import re
import tempfile
import os
import subprocess

def main():
    filepath = r"d:\projects\python\ai-exam-platform\app\static\index.html"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Simple regex to extract script tag contents
    scripts = re.findall(r"<script>(.*?)</script>", content, re.DOTALL)
    print(f"Extracted {len(scripts)} script blocks.")
    
    has_errors = False
    for idx, script in enumerate(scripts):
        if not script.strip():
            continue
        
        # Write to temporary file
        fd, path = tempfile.mkstemp(suffix=".js")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                tmp.write(script)
            
            # Check with node
            res = subprocess.run(["node", "--check", path], capture_output=True, text=True)
            if res.returncode != 0:
                print(f"\n❌ Syntax Error in Script Block #{idx+1}:")
                print(res.stderr)
                has_errors = True
            else:
                print(f"✅ Script Block #{idx+1} is syntax-valid.")
        finally:
            os.remove(path)

    if has_errors:
        print("\nVerification failed: Syntax errors found.")
    else:
        print("\nAll JavaScript blocks are fully valid!")

if __name__ == "__main__":
    main()
