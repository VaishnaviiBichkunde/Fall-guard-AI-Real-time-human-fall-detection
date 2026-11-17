import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

start_idx = None
end_idx = None

for i, l in enumerate(lines):
    if l.strip() == "if active_inc:" and i > 2700 and i < 2750:
        start_idx = i
    if l.strip() == "# 8. QUICK ACTIONS" and i > 2950 and i < 3000:
        end_idx = i - 1
        break

print("start_idx:", start_idx, "end_idx:", end_idx)

if start_idx is not None and end_idx is not None:
    # We want to wrap lines[start_idx:end_idx] with if show_emergency:
    chunk_to_indent = lines[start_idx:end_idx]
    indented_chunk = ["    " + line if line.strip() else line for line in chunk_to_indent]
    
    new_block = ["    if show_emergency:\n", '        st.markdown(\'<h3 style="margin:20px 0 12px 0; font-weight:800; color:#0F172A; font-size:1.35rem;">🚨 Emergency Alerts & Triage</h3>\', unsafe_allow_html=True)\n'] + indented_chunk
    
    lines = lines[:start_idx] + new_block + lines[end_idx:]
    with open("app.py", "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("Indented emergency section successfully under if show_emergency:")
else:
    print("Could not find start/end indices for emergency section.")
