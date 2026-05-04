with open('templates/profile.html', encoding='utf-8') as f:
    c = f.read()

old = '    <div class="m-actions" style="position:sticky;bottom:0;background:var(--bg-card);padding-top:12px;border-top:1px solid var(--border-color)">\n      <button class="m-cancel" onclick="closeEditProfile()">Cancel</button>\n      <button class="m-save" id="btnSaveProfile"><i class="bi bi-check2"></i> Save Profile</button>\n    </div>'

new = '    </div><!-- end scrollable body -->\n    <div style="flex-shrink:0;display:flex;justify-content:flex-end;gap:10px;padding:14px 24px;border-top:1px solid var(--border-color)">\n      <button class="m-cancel" onclick="closeEditProfile()">Cancel</button>\n      <button class="m-save" id="btnSaveProfile">Save Profile</button>\n    </div>'

if old in c:
    print('FOUND - replacing')
    c2 = c.replace(old, new, 1)
    with open('templates/profile.html', 'w', encoding='utf-8') as f:
        f.write(c2)
    print('DONE')
else:
    print('NOT FOUND')
    idx = c.find('btnSaveProfile')
    print(repr(c[idx-300:idx+100]))
