#!/usr/bin/env python3
"""
K2Rebuild - Firmware Validator
Validates BOTH an original/extracted rootfs and a rebuilt Debian rootfs prior to deployment.

What it does (best-effort, non-destructive):
- Safely bind-mounts /proc, /sys, /dev into each rootfs (for chrooted checks)
- Structure checks (key dirs/files), disk space, hostname/hosts
- Python runtime & module checks
- ELF dependency scan (ldd) for missing libs
- Service presence (systemd units / init.d)
- Config linting:
  - nginx -t (if installed)
  - Moonraker YAML parse (if present)
  - Printer config quick existence & Klipper binary sanity
- APT reachability (optional), network ping (optional)
- Kernel modules directory inspection
- File inventory & quick diffs between ORIGINAL and REBUILT
- Emits JSON and Markdown summaries to /work/firmware-test-logs/

This runs inside the K2Rebuild container and requires root privileges for chroot and mounts.
"""

import os, sys, json, subprocess, shutil, time, hashlib, textwrap
from datetime import datetime

LOG_DIR = "/work/firmware-test-logs"
os.makedirs(LOG_DIR, exist_ok=True)

# ---- small helpers -----------------------------------------------------------

def sh(cmd, timeout=60, check=False):
    """Run a host command and return (rc, out)."""
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout)
        return 0, out.decode("utf-8", "ignore")
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return e.returncode, e.output.decode("utf-8", "ignore")
    except Exception as e:
        return 1, str(e)

def chroot_run(root, cmd, timeout=60):
    """Run a command inside a chroot."""
    full = ["chroot", root] + cmd
    return sh(full, timeout=timeout)

def path_exists(root, rel):
    return os.path.exists(os.path.join(root, rel.lstrip("/")))

def file_sha256(path, limit_bytes=0):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            if limit_bytes and limit_bytes > 0:
                h.update(f.read(limit_bytes))
            else:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

# ---- mount manager -----------------------------------------------------------

class Mounts:
    def __init__(self, root):
        self.root = root
        self.did = []

    def _mount(self, args):
        rc, out = sh(args)
        if rc == 0:
            self.did.append(list(args))
        return rc, out

    def setup(self):
        # copy resolv.conf for DNS tests
        try:
            os.makedirs(os.path.join(self.root, "etc"), exist_ok=True)
            if os.path.exists("/etc/resolv.conf"):
                shutil.copy("/etc/resolv.conf", os.path.join(self.root, "etc/resolv.conf"))
        except Exception:
            pass
        self._mount(["mount", "-t", "proc", "proc", os.path.join(self.root, "proc")])
        self._mount(["mount", "-t", "sysfs", "sys", os.path.join(self.root, "sys")])
        self._mount(["mount", "--rbind", "/dev", os.path.join(self.root, "dev")])
        self._mount(["mount", "--rbind", "/dev/pts", os.path.join(self.root, "dev/pts")])

    def teardown(self):
        # unmount in reverse order
        for args in reversed(self.did):
            target = args[-1]
            sh(["umount", "-lf", target])
        self.did = []

# ---- core validator ----------------------------------------------------------

class RootFSValidator:
    def __init__(self, label, root):
        self.label = label
        self.root = os.path.abspath(root)
        self.results = {
            "label": label,
            "root": self.root,
            "timestamp": datetime.utcnow().isoformat()+"Z",
            "tests": {},
            "warnings": [],
            "errors": []
        }
        self.mounts = Mounts(self.root)

    # ---------- TESTS ----------

    def test_structure(self):
        needed_dirs = ["bin","sbin","etc","usr","lib","var"]
        missing = [d for d in needed_dirs if not path_exists(self.root, d)]
        critical_bins = ["/bin/sh", "/usr/bin/python3"]
        missing_bins = [b for b in critical_bins if not path_exists(self.root, b)]
        ok = (len(missing)==0 and len(missing_bins)==0)
        self.results["tests"]["structure"] = {
            "ok": ok, "missing_dirs": missing, "missing_bins": missing_bins
        }
        if not ok:
            self.results["warnings"].append("Basic structure incomplete")

    def test_diskspace(self):
        st = os.statvfs(self.root)
        free_mb = (st.f_bavail * st.f_frsize) / (1024*1024)
        self.results["tests"]["disk_space_mb"] = round(free_mb, 1)
        if free_mb < 200:
            self.results["warnings"].append("Low free space (<200 MB)")

    def test_python_runtime(self):
        rc, out = chroot_run(self.root, ["python3","-V"])
        ok = (rc==0)
        self.results["tests"]["python_runtime"] = {"ok": ok, "version": out.strip()}
        if not ok:
            self.results["errors"].append("Python3 runtime not working")

        # check some helpful modules if present
        mods = ["yaml","requests"]
        mod_res = {}
        for m in mods:
            rc2, out2 = chroot_run(self.root, ["python3","-c", f"import {m}; print('{m}:OK')"])
            mod_res[m] = (rc2==0)
        self.results["tests"]["python_modules"] = mod_res

    def test_services_presence(self):
        candidates = {
            "klipper": ["/etc/systemd/system/klipper.service", "/etc/init.d/klipper", "/usr/local/bin/klippy", "/usr/bin/klippy"],
            "moonraker": ["/etc/systemd/system/moonraker.service", "/etc/init.d/moonraker", "/usr/local/bin/moonraker", "/usr/bin/moonraker"],
            "nginx": ["/etc/systemd/system/nginx.service", "/etc/init.d/nginx", "/usr/sbin/nginx", "/usr/bin/nginx"]
        }
        found = {}
        for svc, paths in candidates.items():
            found[svc] = any(path_exists(self.root, p) for p in paths)
        self.results["tests"]["services_presence"] = found

    def test_nginx_syntax(self):
        if not path_exists(self.root, "/usr/sbin/nginx") and not path_exists(self.root, "/usr/bin/nginx"):
            self.results["tests"]["nginx_test"] = {"skipped": True, "reason": "nginx not present"}
            return
        rc, out = chroot_run(self.root, ["nginx","-t"])
        self.results["tests"]["nginx_test"] = {"ok": (rc==0), "output": out[-4000:]}
        if rc!=0:
            self.results["errors"].append("nginx config test failed")

    def test_moonraker_config(self):
        # try some common locations
        possible = [
            "/etc/moonraker.conf",
            "/usr/data/printer_data/config/moonraker.conf",
            "/data/printer_data/config/moonraker.conf",
        ]
        conf = next((p for p in possible if path_exists(self.root, p)), None)
        if not conf:
            self.results["tests"]["moonraker_config"] = {"skipped": True, "reason": "not found"}
            return
        # YAML parse if PyYAML is present
        rc, out = chroot_run(self.root, ["python3","-c",
            f"import sys; import yaml; yaml.safe_load(open('{conf}','r').read()); print('OK')"])
        ok = (rc==0 and "OK" in out)
        self.results["tests"]["moonraker_config"] = {"ok": ok, "file": conf}
        if not ok:
            self.results["errors"].append("moonraker.conf failed YAML parse")

    def test_klipper_presence(self):
        # best-effort: check for klippy script or module
        bins = ["/usr/local/bin/klippy","/usr/bin/klippy"]
        if any(path_exists(self.root, b) for b in bins):
            rc, out = chroot_run(self.root, ["klippy","--help"])
            self.results["tests"]["klipper_cli"] = {"ok": (rc==0), "output": out[:2000]}
            return
        # module check
        rc, out = chroot_run(self.root, ["python3","-c","import klipper; print('OK')"])
        self.results["tests"]["klipper_module"] = {"present": (rc==0)}
        if rc!=0:
            self.results["warnings"].append("Klipper binary/module not detected")

    def test_network(self):
        # lightweight ping test
        rc, _ = chroot_run(self.root, ["ping","-c","1","8.8.8.8"], timeout=10)
        self.results["tests"]["network_ping"] = {"ok": (rc==0)}
        # DNS test
        rc2, out2 = chroot_run(self.root, ["getent","hosts","creality.com"], timeout=10)
        self.results["tests"]["dns_resolve"] = {"ok": (rc2==0), "output": out2.strip()[:200]}

    def test_apt(self):
        if not path_exists(self.root, "/usr/bin/apt-get"):
            self.results["tests"]["apt"] = {"skipped": True, "reason": "apt-get not present"}
            return
        rc, out = chroot_run(self.root, ["bash","-lc","apt-get update -qq || true && apt-get -qq check || true"], timeout=90)
        ok = ("Reading package lists" in out) or (rc==0)
        self.results["tests"]["apt"] = {"ok": ok, "snippet": out[-2000:]}

    def test_elf_deps(self):
        # scan a limited set for speed
        roots = ["/bin","/sbin","/usr/bin","/usr/sbin"]
        missing = []
        # ensure ldd exists
        if not path_exists(self.root, "/usr/bin/ldd") and not path_exists(self.root, "/bin/ldd"):
            self.results["tests"]["elf_deps"] = {"skipped": True, "reason": "ldd not present"}
            return
        for base in roots:
            ab = os.path.join(self.root, base.lstrip("/"))
            if not os.path.isdir(ab):
                continue
            for name in os.listdir(ab):
                p = os.path.join(ab, name)
                # quick ELF test
                rc, out = sh(["file", p])
                if rc==0 and "ELF" in out and os.access(p, os.X_OK):
                    rc2, out2 = chroot_run(self.root, ["ldd", p])
                    if "not found" in out2:
                        missing.append({ "binary": base+"/"+name, "ldd": out2.strip()[:500] })
        self.results["tests"]["elf_deps"] = {"missing_count": len(missing), "missing": missing[:50]}
        if missing:
            self.results["errors"].append(f"{len(missing)} binaries with missing libraries")

    def test_kernel_modules_dir(self):
        libmods = os.path.join(self.root, "lib/modules")
        if not os.path.isdir(libmods):
            self.results["tests"]["kernel_modules"] = {"present": False}
            self.results["warnings"].append("No /lib/modules directory")
            return
        vers = [d for d in os.listdir(libmods) if os.path.isdir(os.path.join(libmods,d))]
        self.results["tests"]["kernel_modules"] = {"present": True, "versions": vers}

    # ---------- ORCHESTRATION ----------

    def run_all(self):
        self.mounts.setup()
        try:
            self.test_structure()
            self.test_diskspace()
            self.test_python_runtime()
            self.test_services_presence()
            self.test_nginx_syntax()
            self.test_moonraker_config()
            self.test_klipper_presence()
            self.test_network()
            self.test_apt()
            self.test_elf_deps()
            self.test_kernel_modules_dir()
        finally:
            self.mounts.teardown()

    def save_reports(self):
        base = os.path.join(LOG_DIR, f"{self.label}_report")
        # JSON
        with open(base + ".json", "w") as f:
            json.dump(self.results, f, indent=2)
        # Markdown summary
        md = [f"# K2Rebuild Firmware Validation — {self.label}\n",
              f"- Root: `{self.root}`",
              f"- Time: {self.results['timestamp']}",
              f"- Errors: {len(self.results['errors'])}",
              f"- Warnings: {len(self.results['warnings'])}",
              "\n## Summary\n"]
        for k,v in self.results["tests"].items():
            md.append(f"### {k}\n```\n{json.dumps(v, indent=2)}\n```\n")
        if self.results["warnings"]:
            md.append("## Warnings\n")
            for w in self.results["warnings"]:
                md.append(f"- {w}")
        if self.results["errors"]:
            md.append("\n## Errors\n")
            for e in self.results["errors"]:
                md.append(f"- {e}")
        with open(base + ".md", "w") as f:
            f.write("\n".join(md))

def compare_roots(orig_root, new_root):
    """Lightweight inventory diff (counts + lists for critical dirs)."""
    def list_rel(root, sub):
        base = os.path.join(root, sub.lstrip("/"))
        out = []
        if os.path.isdir(base):
            for dirpath, _, files in os.walk(base):
                for name in files:
                    out.append(os.path.relpath(os.path.join(dirpath, name), root))
        return set(out)

    sections = ["/bin","/sbin","/usr/bin","/usr/sbin","/etc","/lib/modules"]
    diff = {}
    for sec in sections:
        a = list_rel(orig_root, sec)
        b = list_rel(new_root, sec)
        added = sorted(list(b - a))[:200]
        removed = sorted(list(a - b))[:200]
        diff[sec] = {
            "added_count": len(b - a),
            "removed_count": len(a - b),
            "added_sample": added,
            "removed_sample": removed
        }
    out_json = os.path.join(LOG_DIR, "inventory_diff.json")
    with open(out_json, "w") as f:
        json.dump(diff, f, indent=2)
    # simple markdown too
    with open(os.path.join(LOG_DIR, "inventory_diff.md"), "w") as f:
        f.write("# Inventory Diff (original → rebuilt)\n\n")
        for sec, d in diff.items():
            f.write(f"## {sec}\n")
            f.write(f"- Added: {d['added_count']}\n- Removed: {d['removed_count']}\n\n")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: firmware_validator.py <original_rootfs_dir> <rebuilt_rootfs_dir>")
        sys.exit(1)

    orig, rebuilt = sys.argv[1], sys.argv[2]
    for label, root in (("original", orig), ("rebuilt", rebuilt)):
        if not os.path.isdir(root):
            print(f"ERROR: rootfs not found: {root}")
            sys.exit(2)

    # Run both
    v1 = RootFSValidator("original", orig)
    v1.run_all(); v1.save_reports()

    v2 = RootFSValidator("rebuilt", rebuilt)
    v2.run_all(); v2.save_reports()

    # Compare inventories
    compare_roots(orig, rebuilt)

    print(f"\n✅ Reports written to: {LOG_DIR}")
    print(" - original_report.json / .md")
    print(" - rebuilt_report.json  / .md")
    print(" - inventory_diff.json  / .md\n")
