"""
setup.py  —  One-time setup for IEG Strategic Initiatives
Run once after copying to C:\\Users\\Chad\\Downloads\\Python\\SLT
"""
import subprocess, sys, shutil
from pathlib import Path

ROOT = Path(__file__).parent

def run(cmd):
    print(f"  → {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def main():
    print("=" * 55)
    print("  IEG Strategic Initiatives — Setup")
    print("=" * 55)

    print("\n[1/3] Installing dependencies...")
    run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])

    print("\n[2/3] Creating .env file...")
    env_src = ROOT / ".env.template"
    env_dst = ROOT / ".env"
    if not env_dst.exists():
        shutil.copy(env_src, env_dst)
        print(f"  ✅ Created .env at {env_dst}")
    else:
        print("  ⏭  .env already exists, skipping.")

    print("\n[3/3] Setting up data folder...")
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)

    csv_dst  = ROOT / "data" / "Strategic_Initiatives_2026.csv"
    if not csv_dst.exists():
        # Look for the export in common locations
        found = list((Path.home() / "Downloads").glob("Strategic_Initiatives_2026*.csv"))
        if found:
            shutil.copy(found[0], csv_dst)
            print(f"  ✅ Copied CSV → data/Strategic_Initiatives_2026.csv")
        else:
            print(f"  ⚠️  CSV not found in Downloads.")
            print(f"     Export from Microsoft Lists → Export to CSV")
            print(f"     Rename to: Strategic_Initiatives_2026.csv")
            print(f"     Save to:   {ROOT / 'data'}")
    else:
        print("  ✅ CSV already in place.")

    print("\n" + "=" * 55)
    print("  ✅ Setup complete!")
    print("=" * 55)
    print(f"""
Next steps:
  1. Start the app:
       python run_service.py start

  2. Open in browser:
       http://localhost:8502

  3. Share on your network:
       http://{{your-machine-ip}}:8502

  To refresh data at any time:
    - Re-export the List from Microsoft Lists → CSV
    - Drop it in data/Strategic_Initiatives_2026.csv
    - Click Refresh Data in the sidebar
    - All your local edits are preserved (stored in data/edits.json)
""")

if __name__ == "__main__":
    main()
