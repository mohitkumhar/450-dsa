
// ── Event Listeners (registered first so Chart.js failure can't break them) ──
document.getElementById('btnSaveProfile').addEventListener('click',function(){
  const btn=this;
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
  btn.disabled=true;
  contentEl.innerHTML='<span class="btn-spinner"></span> Saving...';
  fetch('/edit_profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    .then(r=>r.json())
    .then(res=>{
      if(res.success){
        contentEl.innerHTML='<i class="bi bi-check-lg"></i> Saved!';
        showToast('✅ Profile saved!');
        setTimeout(()=>window.location.reload(),900);
      } else {
        showToast('❌ Error: '+(res.error||'unknown'));
        btn.disabled=false;
        contentEl.innerHTML='<i class="bi bi-check2-circle"></i> Save Profile';
      }
    }).catch(e=>{
      showToast('❌ Network error');
      btn.disabled=false;
      contentEl.innerHTML='<i class="bi bi-check2-circle"></i> Save Profile';
    });
});

document.getElementById('btnSync').addEventListener('click',function(){
  const btn=this;
  const syncContent=document.getElementById('syncBtnContent');
  const lc=document.getElementById('lc_username').value.trim();
  const gh=document.getElementById('gh_username').value.trim();
  const gfg=document.getElementById('gfg_username').value.trim();
  if(!lc && !gh && !gfg){showToast('\u26a0\ufe0f Enter at least one username');return;}

  // Disable button & show spinner
  btn.disabled=true;
  syncContent.innerHTML='<span class="btn-spinner"></span> Syncing...';

  // Show loading overlay
  const overlay=document.getElementById('syncOverlay');
  overlay.style.display='flex';
  document.getElementById('syncOverlayMsg').textContent='Syncing your profiles...';

  // Animate step indicators
  const steps=['ss_lc','ss_gh','ss_gfg'];
  const labels=['LeetCode','GitHub','GFG'];
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

  fetch('/sync_platforms',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({leetcode:lc,github:gh,gfg:gfg}),
    signal:ctrl.signal
  })
  .then(r=>{clearTimeout(timer);return r.json();})
  .then(res=>{
    clearInterval(stepTimer);
    overlay.style.display='none';
    if(res.success){
      syncContent.innerHTML='<i class="bi bi-check-lg"></i> Synced!';
      showToast('\u2705 Synced successfully! Reloading...');
      setTimeout(()=>window.location.reload(),1200);
    }else{
      btn.disabled=false;
      syncContent.innerHTML='<i class="bi bi-arrow-repeat"></i> Sync Activity';
      showToast('\u274c Sync failed: '+(res.error||'unknown'));
    }
  })
  .catch(err=>{
    clearInterval(stepTimer);
    overlay.style.display='none';
    btn.disabled=false;
    syncContent.innerHTML='<i class="bi bi-arrow-repeat"></i> Sync Activity';
    if(err.name==='AbortError'){
      showToast('\u23f0 Sync timed out. Try again.');
    }else{
      showToast('\u274c Network error. Check connection.');
    }
    console.error('Sync error:',err);
  });
});

// ── Chart & Visualization Code ──
const dailyCounts = null;
const heatmap = document.getElementById('heatmap');
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

const ratingHistory = null;
const cumData = null;
const chartCanvas = document.getElementById('progressChart');
const chartData = ratingHistory.length > 0 ? ratingHistory : cumData;
if(chartData.length > 0 && chartCanvas && typeof Chart !== 'undefined'){
  new Chart(chartCanvas,{
    type:'line',
    data:{labels:chartData.map(d=>d.x),datasets:[{data:chartData.map(d=>d.y),borderColor:'#f68b24',backgroundColor:'rgba(246,139,36,.15)',borderWidth:2,fill:true,tension:.4,pointRadius:ratingHistory.length>0?3:0,pointHoverRadius:5,pointBackgroundColor:'#f68b24'}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{title:items=>items[0].label,label:ctx=>ratingHistory.length>0?'Rating: '+ctx.raw:'Solved: '+ctx.raw}}},scales:{x:{grid:{display:false},ticks:{color:'#888',maxTicksLimit:5,font:{size:10}}},y:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#888',font:{size:10}}}}}
  });
} else if(chartCanvas && typeof Chart !== 'undefined') {
  // Show empty state inside canvas area
  const ctx = chartCanvas.getContext('2d');
  ctx.fillStyle = 'rgba(255,255,255,0.08)';
  ctx.fillRect(0,0,chartCanvas.width,chartCanvas.height);
  ctx.fillStyle = '#555';
  ctx.font = '13px Inter, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Sync LeetCode to see rating chart', chartCanvas.width/2, chartCanvas.height/2 - 8);
}

const pData = null;
try{new Chart(document.getElementById('platformsChart'),{
  type:'doughnut',
  data:{labels:['LeetCode','GFG','HackerRank','Other'],datasets:[{data:[pData['LeetCode'],pData['GFG'],pData['HackerRank'],pData['Other']],backgroundColor:['#ffb800','#22c55e','#00bd6c','#6c757d'],borderWidth:0,cutout:'78%'}]},
  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}
});}catch(e){console.warn('Chart.js load failed:',e);}

try{new Chart(document.getElementById('difficultyChart'),{
  type:'doughnut',
  data:{labels:['Easy','Medium','Hard'],datasets:[{data:[null,null,null],backgroundColor:['#00b8a3','#ffc01e','#ff375f'],borderWidth:0,cutout:'78%'}]},
  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}
});}catch(e){console.warn('Difficulty chart error:',e);}

function openSyncModal(){document.getElementById('syncModal').classList.add('open')}
function closeSyncModal(){document.getElementById('syncModal').classList.remove('open')}
function showCodelioCard(){document.getElementById('cardModal').classList.add('open')}
function showToast(msg){
  const t=document.getElementById('toast');
  if(!t)return;
  t.textContent=msg;t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2800);
}
function openEditProfile(){document.getElementById('editProfileModal').classList.add('open')}
function closeEditProfile(){document.getElementById('editProfileModal').classList.remove('open')}

['syncModal','cardModal','editProfileModal'].forEach(id=>{
  const el=document.getElementById(id);
  if(el) el.addEventListener('click',e=>{if(e.target.id===id)el.classList.remove('open');});
});

function handlePhotoUpload(e){
  const file=e.target.files[0];
  if(!file)return;
  if(file.size>2*1024*1024){showToast('❌ Image too large (max 2MB)');return;}
  const preview=document.getElementById('editAvatarPreview');
  const mainAvatar=document.getElementById('avatarRing');
  const fd=new FormData();
  fd.append('photo',file);
  showToast('⏳ Uploading photo...');
  fetch('/upload_photo',{method:'POST',body:fd})
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
}
