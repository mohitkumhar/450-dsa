(function() {
const config = JSON.parse(document.getElementById('profile-config').textContent);
const endpointConfig = config.endpointConfig;
const csrfToken = config.csrfToken;
const userPlatforms = config.userPlatforms;
const dailyCounts = config.dailyCounts;
const ratingHistory = config.ratingHistory;
const cumData = config.cumData;
const pData = config.pData;
const brandColors = config.brandColors;
const difficultyCounts = config.difficultyCounts;

// Sidebar progress card copying
function showProgressCardUrlFallback(url) {
  const fallback = document.getElementById('progress-card-copy-fallback');
  const input = document.getElementById('progress-card-copy-url');
  if (!fallback || !input) return;

  input.value = url;
  fallback.style.display = 'block';
  input.focus();
  input.select();

  if (typeof showToast === 'function') {
    showToast('Could not copy automatically. The URL is selected below.', 'warning');
  }
}

window.copyProgressCardUrl = function() {
  const url = window.location.origin + endpointConfig.publicCardPath;
  if (!navigator.clipboard || typeof navigator.clipboard.writeText !== 'function') {
    showProgressCardUrlFallback(url);
    return;
  }

  navigator.clipboard.writeText(url).then(() => {
    if (typeof showToast === 'function') {
      showToast('Progress Image URL copied!', 'success');
    }
  }).catch(() => {
    showProgressCardUrlFallback(url);
  });
};

// ── Event Listeners (registered first so Chart.js failure can't break them) ──
window.handleSaveProfile = function(btn){
  const contentEl=document.getElementById('saveProfileContent');
  const payload={
    name: document.getElementById('ep_name').value,
    bio: document.getElementById('ep_bio').value,
    headline: document.getElementById('ep_headline').value,
    location: document.getElementById('ep_location').value,
    college: document.getElementById('ep_college').value,
    linkedin_url: document.getElementById('ep_linkedin').value,
    twitter_url: document.getElementById('ep_twitter').value,
    website_url: document.getElementById('ep_website').value,
    resume_url: document.getElementById('ep_resume').value,
  };
  window.setButtonBusyState(btn, contentEl, { busy: true, busyLabel: 'Saving...' });
  fetch(endpointConfig.editProfile,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken},body:JSON.stringify(payload)})
    .then(r=>r.json())
    .then(res=>{
      if(res.success){
        contentEl.innerHTML='<i class="bi bi-check-lg"></i> Saved!';
        showToast('✅ Profile saved!');
        setTimeout(()=>window.location.reload(),900);
      } else {
        showToast('❌ Error: '+(res.error||'unknown'));
        window.setButtonBusyState(btn, contentEl, { busy: false });
      }
    }).catch(e=>{
      showToast('❌ Network error');
      window.setButtonBusyState(btn, contentEl, { busy: false });
    });
};

window.handleQuickSync = function(btn) {
  const icon = document.getElementById('quickSyncIcon');
  if (btn.disabled) return;

  const lc = userPlatforms.leetcode;
  const gh = userPlatforms.github;
  const gfg = userPlatforms.gfg;
  const hr = userPlatforms.hackerrank;
  const cn = userPlatforms.codingninjas;
  const ac = userPlatforms.atcoder;
  const cw = userPlatforms.codewars;

  if(!lc && !gh && !gfg && !hr && !cn && !ac && !cw){
    showToast('⚠️ No platforms connected to sync!');
    return;
  }

  btn.disabled = true;
  window.setIconBusyState(icon, { busy: true, idleClassName: 'bi bi-arrow-clockwise' });
  showToast('⏳ Syncing profiles...');

  fetch(endpointConfig.syncPlatforms, {
    method:'POST',
    headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken},
    body:JSON.stringify({leetcode:lc,github:gh,gfg:gfg,hackerrank:hr,codingninjas:cn,atcoder:ac,codewars:cw})
  })
  .then(r => r.json())
  .then(res => {
    btn.disabled = false;
    window.setIconBusyState(icon, { busy: false });
    if(res.success){
      showToast('✅ Synced successfully! Reloading...');
      setTimeout(()=>window.location.reload(), 1200);
    } else {
      showToast('❌ Sync failed: ' + (res.error || 'unknown'));
    }
  })
  .catch(err => {
    btn.disabled = false;
    window.setIconBusyState(icon, { busy: false });
    showToast('❌ Network error. Check connection.');
  });
};

window.handleSyncProfile = function(btn){
  const syncContent=document.getElementById('syncBtnContent');
  const lc=document.getElementById('lc_username').value.trim();
  const gh=document.getElementById('gh_username').value.trim();
  const gfg=document.getElementById('gfg_username').value.trim();
  const hr=document.getElementById('hr_username').value.trim();
  const cn=document.getElementById('cn_username').value.trim();
  const ac=document.getElementById('ac_username').value.trim();
  const cw=document.getElementById('cw_username').value.trim();
  if(!lc && !gh && !gfg && !hr && !cn && !ac && !cw){showToast('⚠️ Enter at least one username');return;}

  // Disable button & show spinner
  window.setButtonBusyState(btn, syncContent, { busy: true, busyLabel: 'Syncing...' });

  // Show loading overlay
  const overlay=document.getElementById('syncOverlay');
  overlay.style.display='flex';
  document.getElementById('syncOverlayMsg').textContent='Syncing your profiles...';

  // Animate step indicators
  const syncPlatforms=[
    {id:'ss_lc', label:'LeetCode', value:lc},
    {id:'ss_gh', label:'GitHub', value:gh},
    {id:'ss_gfg', label:'GFG', value:gfg},
    {id:'ss_hr', label:'HackerRank', value:hr},
    {id:'ss_cn', label:'Coding Ninjas', value:cn},
    {id:'ss_ac', label:'AtCoder', value:ac},
    {id:'ss_cw', label:'Codewars', value:cw}
  ];
  const activeSyncPlatforms=syncPlatforms.filter(platform=>platform.value);
  const stepsContainer=document.getElementById('syncSteps');
  stepsContainer.innerHTML=activeSyncPlatforms.map((platform,index)=>`
    ${index?'<span style="color:rgba(255,255,255,.2)">·</span>':''}
    <span id="${platform.id}" style="font-size:.75rem;color:rgba(255,255,255,.4)">&#9675; ${platform.label}</span>
  `).join('');

  const steps=activeSyncPlatforms.map(platform=>platform.id);
  const labels=activeSyncPlatforms.map(platform=>platform.label);
  let si=0;
  const stepTimer=setInterval(()=>{
    if(si>0) document.getElementById(steps[si-1]).style.color='rgba(0,200,100,.8)';
    if(si<steps.length){
      document.getElementById(steps[si]).style.color='#fff';
      document.getElementById('syncOverlayMsg').textContent='Syncing '+labels[si]+'...';
      si++;
    }else clearInterval(stepTimer);
  }, 6000);

  // Fetch with 90s timeout
  const ctrl=new AbortController();
  const timer=setTimeout(()=>ctrl.abort(),90000);

  fetch(endpointConfig.syncPlatforms,{
    method:'POST',
    headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken},
    body:JSON.stringify({leetcode:lc,github:gh,gfg:gfg,hackerrank:hr,codingninjas:cn,atcoder:ac,codewars:cw}),
    signal:ctrl.signal
  })
  .then(r=>{clearTimeout(timer);return r.json();})
  .then(res=>{
    clearInterval(stepTimer);
    overlay.style.display='none';
    if(res.success){
      syncContent.innerHTML='<i class="bi bi-check-lg"></i> Synced!';
      showToast('✅ Synced successfully! Reloading...');
      setTimeout(()=>window.location.reload(),1200);
    }else{
      window.setButtonBusyState(btn, syncContent, { busy: false });
      showToast('❌ Sync failed: '+(res.error||'unknown'));
    }
  })
  .catch(err=>{
    clearInterval(stepTimer);
    overlay.style.display='none';
    window.setButtonBusyState(btn, syncContent, { busy: false });
    if(err.name==='AbortError'){
      showToast('⏳ Sync timed out. Try again.');
    }else{
      showToast('❌ Network error. Check connection.');
    }
    console.error('Sync error:',err);
  });
};

const heatmap = document.getElementById('heatmap');
window.exportChart = function(id,file){
  const c=document.getElementById(id);if(!c)return;
  const o=document.createElement('canvas'),x=o.getContext('2d'),a=document.createElement('a');
  o.width=c.width;o.height=c.height;x.fillStyle='#1e2327';x.fillRect(0,0,o.width,o.height);x.drawImage(c,0,0);
  a.download=file;a.href=o.toDataURL('image/png');a.click();
};

function markChartReady(id){
  const shell = document.getElementById(id);
  if (shell) shell.classList.add('is-ready');
}
const today = new Date();
const days = 168;
let start = new Date(); start.setDate(today.getDate() - days + 1);
for(let i=0;i<days;i++){
  let d=new Date(start); d.setDate(d.getDate()+i);
  let ds=d.toISOString().split('T')[0];
  let c=dailyCounts[ds]||0, l=0;
  if(c>0&&c<=2)l=1; else if(c>2&&c<=5)l=2; else if(c>5&&c<=10)l=3; else if(c>10)l=4;
  let el=document.createElement('div');
  el.className='hm-cell'; el.dataset.l=l; el.title=ds+': '+c+' submissions';
  heatmap.appendChild(el);
}

const chartShells=['progressChartShell','platformsChartShell','difficultyChartShell'].map(i=>document.getElementById(i)).filter(Boolean);let chartJsPromise;
function loadChartJs(){return window.Chart?Promise.resolve(window.Chart):chartJsPromise||(chartJsPromise=new Promise((ok,bad)=>{let add=(src,err)=>{let s=document.createElement('script');s.src=src;s.async=true;s.onload=()=>ok(window.Chart);s.onerror=err||bad;document.head.appendChild(s)};add('https://cdn.jsdelivr.net/npm/chart.js',()=>add('https://unpkg.com/chart.js@4/dist/chart.umd.js'))}))}
function renderProfileCharts(){loadChartJs().then(()=>{let c=document.getElementById('progressChart'),d=ratingHistory.length?ratingHistory:cumData;if(d.length&&c)new Chart(c,{type:'line',data:{labels:d.map(x=>x.x),datasets:[{data:d.map(x=>x.y),borderColor:'#f68b24',backgroundColor:'rgba(246,139,36,.15)',borderWidth:2,fill:true,tension:.4,pointRadius:ratingHistory.length?3:0,pointHoverRadius:5,pointBackgroundColor:'#f68b24'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{display:false},ticks:{color:'#888',maxTicksLimit:5,font:{size:10}}},y:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#888',font:{size:10}}}}}});else if(c){let x=c.getContext('2d');x.fillStyle='#555';x.font='13px Inter, sans-serif';x.textAlign='center';x.fillText('Sync LeetCode to see rating chart',c.width/2,c.height/2-8)}markChartReady('progressChartShell');[['platformsChart','platformsChartShell',['LeetCode','GFG','Coding Ninjas','HackerRank','Other'],[pData.LeetCode,pData.GFG,pData['Coding Ninjas'],pData.HackerRank,pData.Other],brandColors],['difficultyChart','difficultyChartShell',['Easy','Medium','Hard'],[difficultyCounts.lcEasy,difficultyCounts.lcMedium,difficultyCounts.lcHard],['#00b8a3','#ffc01e','#ff375f']]].forEach(a=>{try{new Chart(document.getElementById(a[0]),{type:'doughnut',data:{labels:a[2],datasets:[{data:a[3],backgroundColor:a[4],borderWidth:0,cutout:'78%'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}})}catch(e){}markChartReady(a[1])})}).catch(()=>chartShells.forEach(s=>s.classList.add('is-ready')))}
if('IntersectionObserver'in window&&chartShells.length){const io=new IntersectionObserver((e,o)=>{if(e.some(x=>x.isIntersecting)){io.disconnect();renderProfileCharts()}},{rootMargin:'160px'});chartShells.forEach(s=>io.observe(s))}else renderProfileCharts();

window.openSyncModal = function(){document.getElementById('syncModal').classList.add('open')};
window.closeSyncModal = function(){document.getElementById('syncModal').classList.remove('open')};
window.showCodelioCard = function(){document.getElementById('cardModal').classList.add('open')};
window.openEditProfile = function(){document.getElementById('editProfileModal').classList.add('open')};
window.closeEditProfile = function(){document.getElementById('editProfileModal').classList.remove('open')};

['syncModal','cardModal','editProfileModal'].forEach(id=>{
  const el=document.getElementById(id);
  if(el) el.addEventListener('click',e=>{if(e.target.id===id)el.classList.remove('open');});
});

window.handlePhotoUpload = function(e){
  const file=e.target.files[0];
  if(!file)return;
  if(file.size>2*1024*1024){showToast('❌ Image too large (max 2MB)');return;}
  const preview=document.getElementById('editAvatarPreview');
  const mainAvatar=document.getElementById('avatarRing');
  const fd=new FormData();
  fd.append('photo',file);
  showToast('⏳ Uploading photo...');
  fetch(endpointConfig.uploadPhoto,{method:'POST',headers:{'X-CSRFToken':csrfToken},body:fd})
    .then(r=>r.json())
    .then(res=>{
      if(res.success){
        // Safe DOM - create img element without innerHTML
        const makeImg=()=>{const i=document.createElement('img');i.src=res.photo_url;i.style.cssText='width:100%;height:100%;object-fit:cover;border-radius:50%';return i;};
        preview.textContent='';
        preview.appendChild(makeImg());
        if(mainAvatar){mainAvatar.textContent='';const i2=makeImg();i2.style.borderRadius='50%';mainAvatar.appendChild(i2);}
        showToast('✅ Photo updated!');
      } else showToast('❌ '+res.error);
    }).catch(()=>showToast('❌ Upload failed'));
};

// ── College/University Autocomplete ──
(function(){
  const inp = document.getElementById('ep_college');
  const dd = document.getElementById('collegeDropdown');
  if(!inp || !dd) return;
  let timer = null, activeIdx = -1;

  function renderItems(items){
    dd.innerHTML = '';
    activeIdx = -1;
    if(!items.length){ dd.style.display='none'; return; }
    items.forEach((item, i) => {
      const div = document.createElement('div');
      div.style.cssText = 'padding:9px 14px;cursor:pointer;font-size:.83rem;border-bottom:1px solid var(--border-subtle);display:flex;justify-content:space-between;align-items:center;transition:background .15s';
      const spanName = document.createElement('span');
      spanName.style.cssText = 'font-weight:600;color:var(--text-primary)';
      spanName.textContent = item.name;
      const spanCountry = document.createElement('span');
      spanCountry.style.cssText = 'font-size:.72rem;color:var(--text-muted)';
      spanCountry.textContent = item.country;
      div.appendChild(spanName);
      div.appendChild(spanCountry);
      div.dataset.label = item.label;
      div.addEventListener('mouseenter', () => { setActive(i); });
      div.addEventListener('click', () => { inp.value = item.label; dd.style.display='none'; });
      dd.appendChild(div);
    });
    dd.style.display='block';
  }

  function setActive(idx){
    const children = dd.children;
    if(activeIdx >= 0 && activeIdx < children.length) children[activeIdx].style.background = '';
    activeIdx = idx;
    if(activeIdx >= 0 && activeIdx < children.length){
      children[activeIdx].style.background = 'var(--bg-secondary)';
      children[activeIdx].scrollIntoView({block:'nearest'});
    }
  }

  inp.addEventListener('input', function(){
    clearTimeout(timer);
    const q = this.value.trim();
    if(q.length < 2){ dd.style.display='none'; return; }
    timer = setTimeout(() => {
      fetch(endpointConfig.searchUniversities + '?q=' + encodeURIComponent(q))
        .then(r => r.json())
        .then(data => renderItems(data))
        .catch(() => { dd.style.display='none'; });
    }, 300);
  });

  inp.addEventListener('keydown', function(e){
    const children = dd.children;
    if(!children.length || dd.style.display === 'none') return;
    if(e.key === 'ArrowDown'){ e.preventDefault(); setActive(Math.min(activeIdx+1, children.length-1)); }
    else if(e.key === 'ArrowUp'){ e.preventDefault(); setActive(Math.max(activeIdx-1, 0)); }
    else if(e.key === 'Enter' && activeIdx >= 0){
      e.preventDefault();
      inp.value = children[activeIdx].dataset.label;
      dd.style.display='none';
    } else if(e.key === 'Escape'){ dd.style.display='none'; }
  });

  document.addEventListener('click', function(e){
    if(!inp.contains(e.target) && !dd.contains(e.target)) dd.style.display='none';
  });
})();
})();
