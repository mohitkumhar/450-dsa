"""
Fix: Move btnSync and btnSaveProfile event listeners BEFORE chart initialization,
and wrap all new Chart() calls in try/catch.
This ensures buttons work even if Chart.js CDN fails.
"""
import re

with open('templates/profile.html', encoding='utf-8') as f:
    content = f.read()

# --- Step 1: Wrap all new Chart() calls in try/catch ---
content = content.replace(
    "if(chartData.length > 0 && chartCanvas){",
    "if(chartData.length > 0 && chartCanvas && typeof Chart !== 'undefined'){"
)
content = content.replace(
    "} else if(chartCanvas) {",
    "} else if(chartCanvas && typeof Chart !== 'undefined') {"
)

# Wrap platformsChart
content = content.replace(
    "\nnew Chart(document.getElementById('platformsChart'),{",
    "\ntry{new Chart(document.getElementById('platformsChart'),{"
)
content = content.replace(
    "  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}\n});\n\nnew Chart(document.getElementById('difficultyChart')",
    "  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}\n});}catch(e){console.warn('Chart.js load failed:',e);}\n\ntry{new Chart(document.getElementById('difficultyChart')"
)
# Close the difficultyChart try/catch
content = content.replace(
    "  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}\n});\n\nfunction openSyncModal",
    "  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}\n});}catch(e){console.warn('Difficulty chart error:',e);}\n\nfunction openSyncModal"
)

# --- Step 2: Move btnSync and btnSaveProfile listeners BEFORE the chart code ---
# Extract the two addEventListener blocks

# Find and extract btnSaveProfile block
save_pattern = r"document\.getElementById\('btnSaveProfile'\)\.addEventListener\('click',function\(\)\{.*?\}\);"
save_match = re.search(save_pattern, content, re.DOTALL)

# Find and extract btnSync block  
sync_pattern = r"document\.getElementById\('btnSync'\)\.addEventListener\('click',function\(\)\{.*?\}\);"
sync_match = re.search(sync_pattern, content, re.DOTALL)

if save_match and sync_match:
    save_block = save_match.group(0)
    sync_block = sync_match.group(0)
    
    # Remove them from current positions
    content = content.replace('\n' + save_block, '', 1)
    content = content.replace('\n' + sync_block, '', 1)
    
    # Find the insertion point: right before the heatmap code (start of script)
    # Insert after: <script>\n
    insert_after = "{% block scripts %}\n<script>\n"
    heatmap_start = "const dailyCounts"
    
    insert_point = content.find(heatmap_start)
    if insert_point != -1:
        content = (
            content[:insert_point] +
            "// ── Event Listeners (registered first so Chart.js failure can't break them) ──\n" +
            save_block + "\n\n" +
            sync_block + "\n\n" +
            "// ── Chart & Visualization Code ──\n" +
            content[insert_point:]
        )
        print("SUCCESS: Event listeners moved before chart code")
    else:
        print("ERROR: Could not find heatmap insertion point")
else:
    if not save_match:
        print("ERROR: Could not find btnSaveProfile listener")
    if not sync_match:
        print("ERROR: Could not find btnSync listener")

with open('templates/profile.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("File saved. Verifying...")
with open('templates/profile.html', encoding='utf-8') as f:
    c = f.read()
    
script_start = c.find('<script>')
event_pos = c.find("getElementById('btnSync')")
chart_pos = c.find('new Chart')
print(f"Script starts at: {script_start}")
print(f"btnSync listener at: {event_pos}")
print(f"First new Chart() at: {chart_pos}")
print(f"btnSync is BEFORE chart code: {event_pos < chart_pos}")
