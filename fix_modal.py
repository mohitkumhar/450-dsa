import re

with open('templates/profile.html', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Change the modal-bx from overflow:auto to flex column layout
content = content.replace(
    'max-width:540px;max-height:90vh;overflow-y:auto',
    'max-width:540px;max-height:88vh;display:flex;flex-direction:column;padding:0;overflow:hidden'
)

# Fix 2: Change the sticky header div to a non-sticky flex-shrink:0 div with its own padding
content = content.replace(
    'display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;position:sticky;top:0;background:var(--bg-card);padding-bottom:12px;border-bottom:1px solid var(--border-color)',
    'flex-shrink:0;display:flex;justify-content:space-between;align-items:center;padding:18px 24px 14px;border-bottom:1px solid var(--border-color)'
)

# Fix 3: Wrap the body in a scrollable div - insert after the header closing div
# Find the header end and wrap everything until the actions div
old_photo_start = '    <!-- Photo Upload -->'
new_photo_start = '    <div style="flex:1;overflow-y:auto;padding:20px 24px 4px">\n    <!-- Photo Upload -->'
content = content.replace(old_photo_start, new_photo_start, 1)

# Fix 4: Change the sticky actions footer to a proper flex footer
content = content.replace(
    '    <div class="m-actions" style="position:sticky;bottom:0;background:var(--bg-card);padding-top:12px;border-top:1px solid var(--border-color)">\n      <button class="m-cancel" onclick="closeEditProfile()">Cancel</button>\n      <button class="m-save" id="btnSaveProfile">&#10004; Save Profile</button>\n    </div>\n  </div>\n</div>',
    '    </div><!-- end scrollable body -->\n    <div style="flex-shrink:0;display:flex;justify-content:flex-end;gap:10px;padding:14px 24px;border-top:1px solid var(--border-color)">\n      <button class="m-cancel" onclick="closeEditProfile()">Cancel</button>\n      <button class="m-save" id="btnSaveProfile">&#10004; Save Profile</button>\n    </div>\n  </div>\n</div>'
)

# Also remove the old inline padding from the main modal-bx (padding is now on header/body/footer)
# The modal-bx already had padding:28px from the CSS class - override with padding:0
# That's already done in fix 1

with open('templates/profile.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done. Checking result...")
# Verify
with open('templates/profile.html', encoding='utf-8') as f:
    c2 = f.read()
idx = c2.find('editProfileModal')
snippet = c2[idx-2:idx+500]
print(snippet)
