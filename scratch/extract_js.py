import re

with open("app/static/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# Find the main app script block. 
# We look for the script tag starting with <!-- ================== MAIN APP JAVASCRIPT ================== -->
pattern = re.compile(r'<!-- ================== MAIN APP JAVASCRIPT ================== -->\s*<script>(.*?)</script>', re.DOTALL)
match = pattern.search(content)
if match:
    js_content = match.group(1)
    with open("scratch/js_debug.js", "w", encoding="utf-8") as out:
        out.write(js_content)
    print("Extracted JS successfully.")
else:
    print("Could not find the script block.")
