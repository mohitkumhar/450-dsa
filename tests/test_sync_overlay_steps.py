from pathlib import Path


PROFILE_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "profile.html"
PROFILE_JS = Path(__file__).resolve().parents[1] / "static" / "js" / "profile.js"


def test_sync_overlay_includes_all_submitted_platforms():
    js_content = PROFILE_JS.read_text(encoding="utf-8")

    assert "{id:'ss_lc', label:'LeetCode', value:lc}" in js_content
    assert "{id:'ss_gh', label:'GitHub', value:gh}" in js_content
    assert "{id:'ss_gfg', label:'GFG', value:gfg}" in js_content
    assert "{id:'ss_hr', label:'HackerRank', value:hr}" in js_content
    assert "{id:'ss_cn', label:'Coding Ninjas', value:cn}" in js_content
    assert "{id:'ss_ac', label:'AtCoder', value:ac}" in js_content
    assert "{id:'ss_cw', label:'Codewars', value:cw}" in js_content


def test_sync_overlay_steps_are_built_from_active_values():
    js_content = PROFILE_JS.read_text(encoding="utf-8")

    assert "const activeSyncPlatforms=syncPlatforms.filter(platform=>platform.value);" in js_content
    assert "stepsContainer.innerHTML=activeSyncPlatforms.map" in js_content
    assert "const steps=activeSyncPlatforms.map(platform=>platform.id);" in js_content
    assert "const labels=activeSyncPlatforms.map(platform=>platform.label);" in js_content
    assert "const steps=['ss_lc','ss_gh','ss_gfg','ss_cn'];" not in js_content


def test_sync_profile_template_wires_platforms_into_sync_requests():
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")
    js_content = PROFILE_JS.read_text(encoding="utf-8")

    assert 'id="ac_username"' in template
    assert "const ac = '{{ user.atcoder_username or \"\" }}';" in template
    assert 'id="cw_username"' in template
    assert "const cw = '{{ user.codewars_username or \"\" }}';" in template
    assert "body:JSON.stringify({leetcode:lc,github:gh,gfg:gfg,hackerrank:hr,codingninjas:cn,atcoder:ac,codewars:cw})" in template
