from pathlib import Path


PROFILE_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "profile.html"


def test_sync_overlay_includes_all_submitted_platforms():
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    assert "{id:'ss_lc', label:'LeetCode', value:lc}" in template
    assert "{id:'ss_gh', label:'GitHub', value:gh}" in template
    assert "{id:'ss_gfg', label:'GFG', value:gfg}" in template
    assert "{id:'ss_hr', label:'HackerRank', value:hr}" in template
    assert "{id:'ss_cn', label:'Coding Ninjas', value:cn}" in template
    assert "{id:'ss_ac', label:'AtCoder', value:ac}" in template


def test_sync_overlay_steps_are_built_from_active_values():
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    assert "const activeSyncPlatforms=syncPlatforms.filter(platform=>platform.value);" in template
    assert "stepsContainer.innerHTML=activeSyncPlatforms.map" in template
    assert "const steps=activeSyncPlatforms.map(platform=>platform.id);" in template
    assert "const labels=activeSyncPlatforms.map(platform=>platform.label);" in template
    assert "const steps=['ss_lc','ss_gh','ss_gfg','ss_cn'];" not in template


def test_sync_profile_template_wires_atcoder_into_sync_requests():
    template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    assert 'id="ac_username"' in template
    assert "const ac = '{{ user.atcoder_username or \"\" }}';" in template
    assert "body:JSON.stringify({leetcode:lc,github:gh,gfg:gfg,hackerrank:hr,codingninjas:cn,atcoder:ac})" in template
