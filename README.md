# 🧩 K2Rebuild

**K2Rebuild** is an **experimental**, **educational** firmware research toolkit for the **Creality K2 Plus** 3D printer.

It provides a reproducible Docker-based Linux environment for:
- Extracting, inspecting, and rebuilding Creality K2 Plus firmware images.  
- Bootstrapping a clean Debian ARM64 root filesystem.  
- Integrating open-source **Klipper**, **Moonraker**, and **Mainsail** components.  
- Optionally restoring proprietary Creality binaries for compatibility testing.

> ⚠️ **IMPORTANT:**  
> This project is **not endorsed, supported, or affiliated with Creality** in any way.  
> It is intended **solely for research, learning, and personal experimentation** by technically advanced users.  
> **You assume all responsibility for any use, testing, or modification of your printer’s firmware or hardware.**

---

## 🚀 Quick Start

### 1️⃣ Build the environment

```bash
git clone https://github.com/<yourusername>/K2Rebuild.git
cd K2Rebuild
chmod +x build_and_run_fwtool.sh
./build_and_run_fwtool.sh
