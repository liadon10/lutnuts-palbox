let allPals = [];
let currentViewMode = 'grid'; // 'grid' | 'list'
let currentMainView = 'all_pals'; // 'all_pals' | 'synergy_teams'

const WORK_TYPES = [
  { name: 'Kindling', emoji: '🔥' },
  { name: 'Watering', emoji: '💧' },
  { name: 'Planting', emoji: '🌱' },
  { name: 'Generating Electricity', emoji: '⚡' },
  { name: 'Handiwork', emoji: '🔨' },
  { name: 'Gathering', emoji: '🌾' },
  { name: 'Lumbering', emoji: '🪓' },
  { name: 'Mining', emoji: '⛏' },
  { name: 'Medicine Production', emoji: '🧪' },
  { name: 'Cooling', emoji: '❄' },
  { name: 'Transporting', emoji: '📦' },
  { name: 'Farming', emoji: '🐣' }
];

document.addEventListener('DOMContentLoaded', () => {
  fetchPalsData();
  setupEventListeners();
  setupCustomDropdowns();
  setupGridCardClickDelegation();
});

function ensureAllPalsHaveGuids() {
  if (!Array.isArray(allPals)) return;
  allPals.forEach((p, idx) => {
    if (!p.instance_guid) {
      p.instance_guid = `pal-gen-${idx}-${(p.name || '').toLowerCase().replace(/ /g, '-').replace(/['.]/g, '')}`;
    }
  });
}

async function fetchPalsData() {
  // Always clear stale or empty localStorage on startup if present
  const savedData = localStorage.getItem('palbox_custom_pals');
  if (savedData) {
    try {
      const parsed = JSON.parse(savedData);
      if (Array.isArray(parsed) && parsed.length > 0) {
        allPals = parsed;
        console.log(`[Palbox] Loaded ${allPals.length} Pals from localStorage.`);
        ensureAllPalsHaveGuids();
        const totalCountEl = document.getElementById('totalCount');
        if (totalCountEl) totalCountEl.textContent = allPals.length;
        renderMainView();
        return;
      }
    } catch (e) {
      console.error('Error parsing localStorage custom pals:', e);
    }
    localStorage.removeItem('palbox_custom_pals');
  }

  // Helper function to apply PALS_DATA array
  const applyPalsData = (data) => {
    if (Array.isArray(data) && data.length > 0) {
      allPals = data;
      ensureAllPalsHaveGuids();
      const totalCountEl = document.getElementById('totalCount');
      if (totalCountEl) totalCountEl.textContent = allPals.length;
      renderMainView();
      return true;
    }
    return false;
  };

  // 1. FIRST: fetch pals.json directly (bypasses script caching/race condition)
  try {
    const response = await fetch('pals.json?v=' + Date.now());
    if (response.ok) {
      const jsonPals = await response.json();
      if (applyPalsData(jsonPals)) return;
    }
  } catch (err) {
    console.warn('Fetch pals.json failed, trying window.PALS_DATA:', err);
  }

  // 2. Poll for window.PALS_DATA (up to 10 seconds)
  for (let i = 0; i < 100; i++) {
    await new Promise(r => setTimeout(r, 100));
    if (applyPalsData(window.PALS_DATA)) return;
  }

  // 3. Fallback: Dynamically load pals.js
  try {
    await loadScript('pals.js');
    if (applyPalsData(window.PALS_DATA)) return;
  } catch (err) {
    console.warn('loadScript("pals.js") failed:', err);
  }

  // 4. Fallback: fetch pals.json for web server
  try {
    const response = await fetch('pals.json');
    if (response.ok) {
      const jsonPals = await response.json();
      if (applyPalsData(jsonPals)) return;
    }
  } catch (err) {
    console.warn('Fetch pals.json failed:', err);
  }

  const gridEl = document.getElementById('palGrid');
  if (gridEl) {
    gridEl.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 48px; color: var(--text-muted);">
        <h3>⚠️ Could not load Pal data</h3>
        <p>Make sure <code>Dashboard/pals.js</code> is present.</p>
        <button onclick="localStorage.clear(); location.reload();" style="margin-top:16px; padding:8px 16px; background:var(--accent-blue); color:white; border:none; border-radius:6px; cursor:pointer;">Clear Cache & Reload</button>
      </div>
    `;
  }
}

function getSynergyTeamsData() {
  const savedTeams = localStorage.getItem('synergy_custom_teams');
  if (savedTeams) {
    try {
      const parsed = JSON.parse(savedTeams);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    } catch (e) {
      console.error('Error parsing custom teams:', e);
    }
  }
  return window.SYNERGY_TEAMS || [];
}

function savePalsState() {
  localStorage.setItem('palbox_custom_pals', JSON.stringify(allPals));
}

function saveTeamsState(teams) {
  localStorage.setItem('synergy_custom_teams', JSON.stringify(teams));
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

function toggleCustomDropdown(e, optionsContainerId) {
  if (e) e.stopPropagation();
  const targetContainer = document.getElementById(optionsContainerId);
  const allContainers = document.querySelectorAll('.custom-select-options');
  
  allContainers.forEach(container => {
    if (container !== targetContainer) {
      container.classList.remove('open');
    }
  });

  if (targetContainer) {
    targetContainer.classList.toggle('open');
  }
}

function selectCustomDropdownOption(e, optionsContainerId, hiddenInputId, selectedDisplayId, value, optionEl) {
  if (e) e.stopPropagation();
  const hiddenInput = document.getElementById(hiddenInputId);
  const selectedSpan = document.getElementById(selectedDisplayId);
  const optionsContainer = document.getElementById(optionsContainerId);

  if (hiddenInput) hiddenInput.value = value;
  if (selectedSpan && optionEl) selectedSpan.innerHTML = optionEl.innerHTML;

  if (optionsContainer) {
    const allOptions = optionsContainer.querySelectorAll('.custom-option');
    allOptions.forEach(opt => opt.classList.remove('active'));
    if (optionEl) optionEl.classList.add('active');
    optionsContainer.classList.remove('open');
  }

  renderMainView();
}

function toggleElemDropdown(e) {
  toggleCustomDropdown(e, 'elemDropdownOptions');
}

function selectElemFilter(e, elemValue, optionEl) {
  selectCustomDropdownOption(e, 'elemDropdownOptions', 'elemFilter', 'elemDropdownSelected', elemValue, optionEl);
}

window.toggleCustomDropdown = toggleCustomDropdown;
window.selectCustomDropdownOption = selectCustomDropdownOption;
window.toggleElemDropdown = toggleElemDropdown;
window.selectElemFilter = selectElemFilter;

function setupCustomDropdowns() {
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.custom-select-wrapper')) {
      document.querySelectorAll('.custom-select-options.open').forEach(menu => {
        menu.classList.remove('open');
      });
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.custom-select-options.open').forEach(menu => {
        menu.classList.remove('open');
      });
    }
  });
}



function handlePalCardClick(e, guid) {
  if (!guid) return;
  if (e.target.closest('.card-edit-btn') || 
      e.target.closest('.portrait-link') || 
      e.target.closest('.table-portrait-link') || 
      e.target.closest('.inline-location-select') ||
      e.target.closest('.inline-location-select-table') ||
      e.target.closest('select') ||
      e.target.closest('a')) {
    return;
  }
  openPalDetailModal(guid);
}

function setupGridCardClickDelegation() {
  const grid = document.getElementById('palGrid');
  if (!grid) return;

  grid.addEventListener('click', (e) => {
    if (e.target.closest('.card-edit-btn') || 
        e.target.closest('.portrait-link') || 
        e.target.closest('.table-portrait-link') || 
        e.target.closest('.inline-location-select') ||
        e.target.closest('.inline-location-select-table') ||
        e.target.closest('select') ||
        e.target.closest('a')) {
      return;
    }

    const card = e.target.closest('.pal-card, .pal-list-table tbody tr');
    if (card) {
      const guid = card.getAttribute('data-guid') || card.dataset.guid;
      if (guid) {
        openPalDetailModal(guid);
      }
    }
  });
}

function setupEventListeners() {
  const inputs = ['searchInput', 'locationFilter', 'rankFilter', 'sortSelect'];
  inputs.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', renderMainView);
  });

  const addBtn = document.getElementById('addPalBtn');
  if (addBtn) addBtn.addEventListener('click', openAddModal);

  const addTeamBtn = document.getElementById('addTeamBtn');
  if (addTeamBtn) addTeamBtn.addEventListener('click', openAddSynergyTeamModal);

  const syncMyPalsBtn = document.getElementById('syncMyPalsBtn') || document.getElementById('syncPalsBtn');
  if (syncMyPalsBtn) syncMyPalsBtn.addEventListener('click', syncToMyPalsTable);

  const syncSaveBtn = document.getElementById('syncSaveBtn');
  if (syncSaveBtn) syncSaveBtn.addEventListener('click', syncFromSaveFile);

  const gridBtn = document.getElementById('gridModeBtn');
  const listBtn = document.getElementById('listModeBtn');

  if (gridBtn) {
    gridBtn.addEventListener('click', () => {
      currentViewMode = 'grid';
      gridBtn.classList.add('active');
      if (listBtn) listBtn.classList.remove('active');
      renderMainView();
    });
  }

  if (listBtn) {
    listBtn.addEventListener('click', () => {
      currentViewMode = 'list';
      listBtn.classList.add('active');
      if (gridBtn) gridBtn.classList.remove('active');
      renderMainView();
    });
  }

  const synergyBtn = document.getElementById('synergyViewBtn');
  if (synergyBtn) {
    synergyBtn.addEventListener('click', () => {
      if (currentMainView === 'all_pals') {
        currentMainView = 'synergy_teams';
        synergyBtn.classList.add('active');
        synergyBtn.innerHTML = '🐾 All Pals View';
      } else {
        currentMainView = 'all_pals';
        synergyBtn.classList.remove('active');
        synergyBtn.innerHTML = '⚔️ Combat Teams';
      }
      renderMainView();
    });
  }

  const closeBtn = document.getElementById('modalCloseBtn');
  if (closeBtn) closeBtn.addEventListener('click', closeModal);

  const cancelBtn = document.getElementById('modalCancelBtn');
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

  const deleteBtn = document.getElementById('deletePalBtn');
  if (deleteBtn) deleteBtn.addEventListener('click', deletePalFromModal);

  const form = document.getElementById('palForm');
  if (form) form.addEventListener('submit', savePalFromModal);

  const teamCloseBtn = document.getElementById('teamModalCloseBtn');
  if (teamCloseBtn) teamCloseBtn.addEventListener('click', closeTeamModal);

  const teamCancelBtn = document.getElementById('teamModalCancelBtn');
  if (teamCancelBtn) teamCancelBtn.addEventListener('click', closeTeamModal);

  const deleteTeamBtn = document.getElementById('deleteTeamBtn');
  if (deleteTeamBtn) deleteTeamBtn.addEventListener('click', deleteTeamFromModal);

  const teamForm = document.getElementById('teamForm');
  if (teamForm) teamForm.addEventListener('submit', saveTeamFromModal);

  const detailCloseBtn = document.getElementById('detailModalCloseBtn');
  if (detailCloseBtn) detailCloseBtn.addEventListener('click', closePalDetailModal);

  const detailCloseBottomBtn = document.getElementById('detailModalCloseBottomBtn');
  if (detailCloseBottomBtn) detailCloseBottomBtn.addEventListener('click', closePalDetailModal);

  const modalOverlay = document.getElementById('palModal');
  if (modalOverlay) {
    modalOverlay.addEventListener('click', (e) => {
      if (e.target === modalOverlay) closeModal();
    });
  }

  const teamModalOverlay = document.getElementById('teamModal');
  if (teamModalOverlay) {
    teamModalOverlay.addEventListener('click', (e) => {
      if (e.target === teamModalOverlay) closeTeamModal();
    });
  }

  const detailModalOverlay = document.getElementById('palDetailModal');
  if (detailModalOverlay) {
    detailModalOverlay.addEventListener('click', (e) => {
      if (e.target === detailModalOverlay) closePalDetailModal();
    });
  }
}


async function syncFromSaveFile() {
  const btn = document.getElementById('syncSaveBtn');
  const originalText = btn ? btn.innerHTML : '🔄 Sync from Save';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⌛ Scanning Save & Syncing...';
  }

  try {
    const response = await fetch('/api/run-palworld-sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    if (response.ok) {
      const resData = await response.json();
      // Clear any cached offline data to ensure fresh save data is loaded
      localStorage.removeItem('palbox_custom_pals');
      await fetchPalsData();
      alert(`✅ ${resData.message || 'Successfully scanned save game, updated Google Sheets, and synced Dashboard!'}`);
    } else {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.message || `HTTP ${response.status}`);
    }
  } catch (err) {
    console.error('Error running save file sync:', err);
    alert(`⚠️ Could not complete save file sync:\n${err.message || err}\n\nMake sure the local dashboard server is running.`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }
}


async function syncToMyPalsTable() {
  const syncBtn = document.getElementById('syncMyPalsBtn');
  const originalText = syncBtn ? syncBtn.innerHTML : '☁️ Sync to My Pals';

  if (syncBtn) {
    syncBtn.disabled = true;
    syncBtn.innerHTML = '⌛ Syncing to My Pals...';
  }

  savePalsState();

  try {
    const response = await fetch('/api/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(allPals)
    });

    if (response.ok) {
      const resData = await response.json();
      alert(`✅ ${resData.message || "Successfully updated 'My Pals' Google Sheet table!"}`);
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (err) {
    console.warn('Backend server API not reachable (file:// mode). Exporting local pals.json:', err);
    exportPalsToJSON();
    alert("💾 Saved updated Pal data to your local Dashboard/pals.json!\n\nTo upload your edits directly to Google Sheets 'My Pals' table, run:\npython Scripts/sync_dashboard_to_sheet.py");
  } finally {
    if (syncBtn) {
      syncBtn.disabled = false;
      syncBtn.innerHTML = originalText;
    }
  }
}

function exportPalsToJSON() {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(allPals, null, 2));
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", "pals.json");
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
}

/* ==========================================================================
   PALWORLD.GG URL SLUG GENERATOR
   ========================================================================== */

function getPalworldGgURL(palName) {
  if (!palName) return 'https://palworld.gg';
  const cleanName = palName.replace(/\s*\(.*?\)/g, '').trim().toLowerCase();
  const slug = cleanName.replace(/ /g, '-').replace(/['.]/g, '');
  return `https://palworld.gg/pal/${slug}`;
}

/* ==========================================================================
   EXPANDED PAL DETAIL VIEW MODAL
   ========================================================================== */

let currentDetailPalName = null;

function openPalDetailModal(identifier) {
  if (!identifier) return;

  const pal = allPals.find(p => p.instance_guid === identifier || p.name === identifier || p.paldeck_num === identifier);
  if (!pal) return;

  const portraitSrc = getPalPortraitURL(pal);
  const palName = pal.name || 'Unknown Pal';
  const paldeckNum = pal.paldeck_num || '#???';
  const palLevel = pal.level ? `Lv. ${pal.level}` : 'Lv. ?';
  const starDisplay = pal.stars || '-';
  const palGgURL = getPalworldGgURL(palName);

  const elem1Class = getElementBadgeClass(pal.element1);
  const elem1Icon = getElementIconHTML(pal.element1);
  const elem1Tooltip = getElementTooltipHTML(pal.element1);
  let typeHTML = `<span class="elem-badge ${elem1Class} has-tooltip" style="font-size:0.85rem; padding:4px 10px;">${elem1Icon} ${pal.element1}${elem1Tooltip}</span>`;
  if (pal.element2) {
    const elem2Class = getElementBadgeClass(pal.element2);
    const elem2Icon = getElementIconHTML(pal.element2);
    const elem2Tooltip = getElementTooltipHTML(pal.element2);
    typeHTML += ` <span class="elem-badge ${elem2Class} has-tooltip" style="font-size:0.85rem; padding:4px 10px;">${elem2Icon} ${pal.element2}${elem2Tooltip}</span>`;
  }

  let genderHTML = '⚪ N/A';
  if (pal.gender === 'male') genderHTML = '♂ Male';
  else if (pal.gender === 'female') genderHTML = '♀ Female';

  const partnerInfo = getPartnerSkillInfo(pal);
  const rankTooltipHTML = getRankTooltipHTML(starDisplay);

  const totalOwnedCount = allPals.filter(p => p.name && p.name.toLowerCase() === palName.toLowerCase()).length;
  const countText = `📦 Total Owned in Palbox: ${totalOwnedCount}`;

  // Render Header Info Banner
  const headerBanner = document.getElementById('palDetailHeaderBanner');
  if (headerBanner) {
    headerBanner.innerHTML = `
      <div class="pal-detail-hero">
        <img class="detail-portrait-large" src="${portraitSrc}" alt="${palName}" onerror="this.src='https://raw.githubusercontent.com/palworld-modding/icons/main/pals/lamball.png';">
        <div class="detail-hero-info">
          <div class="detail-hero-title-row">
            <span class="detail-pal-name">${palName}</span>
            ${typeHTML}
            ${pal.is_boss ? `<span class="detail-meta-pill" style="color:#ef4444; border-color:rgba(239,68,68,0.4); display:inline-flex; align-items:center; gap:6px;"><img class="alpha-badge-icon" style="width:18px; height:18px;" src="Images/Icons/PalWorld/Misc/PNG/Alpha_Pals_icon.png" alt="Alpha"> Alpha Pal (Boss)</span>` : ''}
          </div>
          <div class="detail-meta-tags">
            <span class="detail-meta-pill">Paldeck ${paldeckNum}</span>
            <span class="detail-meta-pill">${palLevel}</span>
            <span class="detail-meta-pill badge-rank has-tooltip" style="display:inline-flex;">${starDisplay}${rankTooltipHTML}</span>
            <span class="detail-meta-pill">${genderHTML}</span>
            <span class="detail-meta-pill">📍 ${pal.location || 'Palbox Storage'}</span>
            <span class="detail-meta-pill detail-capture-pill">${countText}</span>
          </div>
        </div>
      </div>
    `;
  }

  // Talent IVs
  let ivsHTML = '';
  if (pal.hp_iv !== undefined || pal.melee_iv !== undefined || pal.def_iv !== undefined) {
    const hpIv = pal.hp_iv || 0;
    const meleeIv = pal.melee_iv || 0;
    const shotIv = pal.shot_iv || 0;
    const defIv = pal.def_iv || 0;

    ivsHTML = `
      <div class="pal-detail-section">
        <div class="detail-section-header">📊 Talent IV Stats</div>
        <div class="iv-bars-grid">
          <div class="iv-item">
            <div class="iv-label-row"><span>HP Talent</span><span>${hpIv}%</span></div>
            <div class="iv-bar-bg"><div class="iv-bar-fill" style="width:${hpIv}%; background:#ef4444;"></div></div>
          </div>
          <div class="iv-item">
            <div class="iv-label-row"><span>Melee ATK</span><span>${meleeIv}%</span></div>
            <div class="iv-bar-bg"><div class="iv-bar-fill" style="width:${meleeIv}%; background:#f59e0b;"></div></div>
          </div>
          <div class="iv-item">
            <div class="iv-label-row"><span>Shot ATK</span><span>${shotIv}%</span></div>
            <div class="iv-bar-bg"><div class="iv-bar-fill" style="width:${shotIv}%; background:#3b82f6;"></div></div>
          </div>
          <div class="iv-item">
            <div class="iv-label-row"><span>Defense</span><span>${defIv}%</span></div>
            <div class="iv-bar-bg"><div class="iv-bar-fill" style="width:${defIv}%; background:#10b981;"></div></div>
          </div>
        </div>
      </div>
    `;
  }

  // Active Skills
  const activeSkills = pal.active_skills || [];
  const activeSkillsHTML = activeSkills.length > 0
    ? activeSkills.map(skill => `<span class="active-skill-pill">⚡ ${skill}</span>`).join('')
    : `<span style="color:var(--text-muted); font-size:0.85rem;">No active combat skills listed.</span>`;

  // Passives Grid
  const passives = [...(pal.passive_skills || [])];
  while (passives.length < 4) {
    passives.push({ name: '-', tier: 0 });
  }

  const passivesHTML = passives.slice(0, 4).map(p => {
    if (!p.name || p.name === '-') return `<div class="passive-pill passive-empty">-</div>`;
    let tierClass = 'passive-tier-0';
    if (p.tier >= 3) tierClass = 'passive-tier-3';
    else if (p.tier === 2) tierClass = 'passive-tier-2';
    else if (p.tier === 1) tierClass = 'passive-tier-1';
    else if (p.tier < 0) tierClass = 'passive-tier-neg';

    const db = window.PASSIVES_DB || {};
    const info = db[p.name.toLowerCase()] || {};
    const effectDesc = info.effects ? `: ${info.effects}` : '';

    return `
      <div class="passive-pill ${tierClass}" style="padding:8px 12px; height:auto; justify-content:flex-start;">
        <strong>${p.name}</strong> ${effectDesc}
      </div>
    `;
  }).join('');

  // Work Suitabilities
  const workBadgesHTML = (pal.work_suitabilities || []).map(w => {
    const iconImg = getWorkIconHTML(w.emoji);
    const fullName = getWorkFullName(w.emoji);
    return `
      <span class="work-badge" style="font-size:0.85rem; padding:6px 12px;">
        ${iconImg} ${fullName}: Level ${w.level}
      </span>
    `;
  }).join('') || `<span style="color:var(--text-muted); font-size:0.85rem;">No work suitabilities.</span>`;

  // Item Drops
  const dropsSpawnsDB = window.PAL_DROPS_SPAWNS_DB || {};
  const palExtra = dropsSpawnsDB[palName] || { drops: [] };
  const palDrops = palExtra.drops || [];

  let dropsHTML = '';
  if (palDrops.length > 0) {
    dropsHTML = palDrops.map(d => `
      <div class="drop-card">
        <img class="drop-item-img" src="${d.icon}" alt="${d.name}" onerror="this.src='https://raw.githubusercontent.com/palworld-modding/icons/main/pals/lamball.png';">
        <div class="drop-card-info">
          <div class="drop-item-name">${d.name}</div>
          <div class="drop-item-meta">
            <span>Qty: <strong>${d.amount}</strong></span>
            <span class="drop-rate-badge">Rate: ${d.rate}</span>
          </div>
        </div>
      </div>
    `).join('');
  } else {
    dropsHTML = `<div style="color:var(--text-muted); font-size:0.85rem; padding:12px;">No special item drops recorded for ${palName}.</div>`;
  }

  currentDetailPalName = palName;

  // Populate Details Body
  const bodyStats = document.getElementById('palDetailBodyStats');
  if (bodyStats) {
    bodyStats.innerHTML = `
      ${ivsHTML}

      <div class="pal-detail-section">
        <div class="detail-section-header">⚡ Partner Skill</div>
        <div style="font-size:0.95rem; font-weight:700; color:#c084fc;">
          ${partnerInfo.name} <span class="partner-rank-tag">Rank ${partnerInfo.rank} (${partnerInfo.rank === 1 ? '0★' : (partnerInfo.rank - 1) + '★'})</span>
          ${partnerInfo.activeValue ? `<span style="margin-left:8px; font-size:0.8rem; background:rgba(192, 132, 252, 0.2); border:1px solid #c084fc; color:#e9d5ff; padding:2px 8px; border-radius:12px;">Active: ${partnerInfo.activeValue}</span>` : ''}
        </div>
        <div style="font-size:0.85rem; color:#cbd5e1; margin-top:4px; line-height:1.4;">
          ${partnerInfo.desc}
        </div>
        ${partnerInfo.rankBreakdownHTML || ''}
      </div>

      <div class="pal-detail-section">
        <div class="detail-section-header">⚔️ Active Combat Skills</div>
        <div class="active-skills-list">
          ${activeSkillsHTML}
        </div>
      </div>

      <div class="pal-detail-section">
        <div class="detail-section-header">🌟 Passive Skills</div>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:10px;">
          ${passivesHTML}
        </div>
      </div>

      <div class="pal-detail-section">
        <div class="detail-section-header">🔨 Work Suitabilities</div>
        <div style="display:flex; flex-wrap:wrap; gap:8px;">
          ${workBadgesHTML}
        </div>
      </div>

      <div class="pal-detail-section">
        <div class="detail-section-header">🎁 Possible Item Drops</div>
        <div class="drops-grid">
          ${dropsHTML}
        </div>
      </div>
    `;
  }

  document.getElementById('detailPalTitle').textContent = `🐾 ${palName} Details`;
  
  const ggBtn = document.getElementById('detailPalGgBtn');
  if (ggBtn) ggBtn.href = palGgURL;

  const editBtn = document.getElementById('detailEditPalBtn');
  if (editBtn) {
    editBtn.onclick = () => {
      closePalDetailModal();
      openEditModal(pal.instance_guid);
    };
  }

  document.getElementById('palDetailModal').style.display = 'flex';
}

function closePalDetailModal() {
  const modal = document.getElementById('palDetailModal');
  if (modal) modal.style.display = 'none';
}

/* ==========================================================================
   TOOLTIPS FOR EVERYTHING (RANK, TYPE, PASSIVE, WORK, LOCATION)
   ========================================================================== */

function getWorkFullName(emojiOrName) {
  const e = emojiOrName || '';
  const found = WORK_TYPES.find(w => e.includes(w.emoji) || e.includes(w.name));
  return found ? found.name : e;
}

function getWorkIconHTML(emojiOrName) {
  const e = emojiOrName || '';
  let filename = '';

  if (e.includes('🔥') || e.includes('Kindling')) filename = 'v1Kindling.png';
  else if (e.includes('💧') || e.includes('Watering')) filename = 'v1Watering.png';
  else if (e.includes('🌱') || e.includes('Planting')) filename = 'v1Planting.png';
  else if (e.includes('⚡') || e.includes('Electricity')) filename = 'v1Generating Electricity.png';
  else if (e.includes('🔨') || e.includes('Handiwork')) filename = 'v1Handiwork.png';
  else if (e.includes('🌾') || e.includes('Gathering')) filename = 'v1Gathering.png';
  else if (e.includes('🪓') || e.includes('Lumbering')) filename = 'v1Lumbering.png';
  else if (e.includes('⛏') || e.includes('Mining')) filename = 'v1Mining.png';
  else if (e.includes('🧪') || e.includes('Medicine')) filename = 'v1Medicine Production.png';
  else if (e.includes('❄') || e.includes('Cooling')) filename = 'v1Cooling.png';
  else if (e.includes('📦') || e.includes('Transporting')) filename = 'v1Transporting.png';
  else if (e.includes('🐣') || e.includes('Farming')) filename = 'v1Farming.png';

  if (filename) {
    const src = `Images/Icons/PalWorld/WorkSymbols/PNG/${encodeURIComponent(filename)}`;
    return `<img class="custom-icon-img" src="${src}" alt="${e}" onerror="this.style.display='none'">`;
  }
  return '';
}

function getElementIconHTML(elem) {
  if (!elem) return '';
  const clean = elem.trim();
  const validElements = ['Dark', 'Dragon', 'Electric', 'Fire', 'Grass', 'Ground', 'Ice', 'Neutral', 'Water'];
  
  for (const v of validElements) {
    if (clean.toLowerCase().includes(v.toLowerCase())) {
      const src = `Images/Icons/PalWorld/PalElements/PNG/Colored-${v}.png`;
      return `<img class="custom-icon-img" src="${src}" alt="${v}" onerror="this.style.display='none'">`;
    }
  }
  return '';
}

function getElementTooltipHTML(elem) {
  if (!elem) return '';
  const lower = elem.toLowerCase();
  let desc = `${elem} Element Pal`;
  if (lower.includes('fire')) desc = 'Fire Element: Deals +20% vs Grass & Ice. Weak vs Water.';
  else if (lower.includes('water')) desc = 'Water Element: Deals +20% vs Fire. Weak vs Electric.';
  else if (lower.includes('grass')) desc = 'Grass Element: Deals +20% vs Ground. Weak vs Fire.';
  else if (lower.includes('electric')) desc = 'Electric Element: Deals +20% vs Water. Weak vs Ground.';
  else if (lower.includes('ice')) desc = 'Ice Element: Deals +20% vs Dragon. Weak vs Fire.';
  else if (lower.includes('ground')) desc = 'Ground Element: Deals +20% vs Electric. Weak vs Grass.';
  else if (lower.includes('dragon')) desc = 'Dragon Element: Deals +20% vs Dark. Weak vs Ice.';
  else if (lower.includes('dark')) desc = 'Dark Element: Deals +20% vs Neutral. Weak vs Dragon.';
  else if (lower.includes('neutral')) desc = 'Neutral Element: Deals normal damage. Weak vs Dark.';

  return `
    <div class="tooltip-popup">
      <span class="tooltip-title">${elem} Type</span>
      <span class="tooltip-effect">${desc}</span>
    </div>
  `;
}

function getRankTooltipHTML(stars) {
  const tooltips = {
    '★★★★': 'Rank 4 (MAX): All Work Suitabilities +1 Level, Partner Skill Level 5 (MAX), HP/ATK/DEF +20%.',
    '★★★': 'Rank 3: Partner Skill Level 4, HP/ATK/DEF +15%.',
    '★★': 'Rank 2: Partner Skill Level 3, HP/ATK/DEF +10%.',
    '★': 'Rank 1: Partner Skill Level 2, HP/ATK/DEF +5%.',
    '-': 'Rank 0: Base Pal stats. Condense at Pal Condenser to raise rank & Partner Skill.'
  };
  const desc = tooltips[stars] || 'Pal Condensation Rank.';
  return `
    <div class="tooltip-popup">
      <span class="tooltip-title">Condensation ${stars || 'Base'}</span>
      <span class="tooltip-effect">${desc}</span>
    </div>
  `;
}

function getLocationSvg(loc) {
  if (!loc) return '<span style="font-size:1.1rem">📦</span>';
  if (loc.includes('Party')) {
    return `<svg class="svg-icon svg-icon-lg" viewBox="0 0 24 24"><path fill="#60a5fa" d="M6.92 5L5 6.92l5.06 5.06L4.1 17.94l1.96 1.96 5.96-5.96L17.08 19 19 17.08l-5.06-5.06 5.96-5.96-1.96-1.96-5.96 5.96z"/></svg>`;
  }
  if (loc.includes('Base')) {
    return `<svg class="svg-icon svg-icon-lg" viewBox="0 0 24 24"><path fill="#4ade80" d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>`;
  }
  if (loc.includes('Global')) {
    return `<svg class="svg-icon svg-icon-lg" viewBox="0 0 24 24"><path fill="#c084fc" d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1a2 2 0 0 0 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3a1 1 0 0 0-1-1H8v-2h2a1 1 0 0 0 1-1V7h2a2 2 0 0 0 2-2v-.41a7.98 7.98 0 0 1 4.9 10.34z"/></svg>`;
  }
  return `<svg class="svg-icon svg-icon-lg" viewBox="0 0 24 24"><path fill="#a7f3d0" d="M20 8l-8-5-8 5v8l8 5 8-5V8zm-8-3l5.5 3.4L12 12 6.5 8.4 12 5z"/></svg>`;
}

function getLocationTooltipHTML(loc) {
  const text = loc || 'Palbox Storage';
  let desc = 'Stored safely in local Palbox.';
  if (text.includes('Party')) desc = 'Active combat team member (Slots 1-5).';
  else if (text.includes('Base')) desc = 'Working Pal deployed at Base Camp.';
  else if (text.includes('Global')) desc = 'Stored in Global Palbox Storage.';
  return `
    <div class="tooltip-popup">
      <span class="tooltip-title">${text}</span>
      <span class="tooltip-effect">${desc}</span>
    </div>
  `;
}

function getElementBadgeClass(elem) {
  if (!elem) return 'elem-neutral';
  const lower = elem.toLowerCase();
  if (lower.includes('fire')) return 'elem-fire';
  if (lower.includes('water')) return 'elem-water';
  if (lower.includes('grass')) return 'elem-grass';
  if (lower.includes('electric')) return 'elem-electric';
  if (lower.includes('ice')) return 'elem-ice';
  if (lower.includes('ground')) return 'elem-ground';
  if (lower.includes('dragon')) return 'elem-dragon';
  if (lower.includes('dark')) return 'elem-dark';
  return 'elem-neutral';
}

function getPassiveTooltipHTML(passiveName) {
  if (!passiveName || passiveName === '-') return '';
  const db = window.PASSIVES_DB || {};
  const info = db[passiveName.toLowerCase()];
  if (!info) return '';

  const rankStr = info.rank ? ` (${info.rank})` : '';
  const effectStr = info.effects || 'No description available.';

  return `
    <div class="tooltip-popup">
      <span class="tooltip-title">${info.name || passiveName}${rankStr}</span>
      <span class="tooltip-effect">${effectStr}</span>
    </div>
  `;
}

function formatPartnerSkillRankBreakdown(desc, activeRankIndex) {
  if (!desc) return { html: '', activeValue: '' };
  const matches = [...desc.matchAll(/(\d+(?:\.\d+)?)\s*[~-]\s*(\d+(?:\.\d+)?)(%|\s*multiplier|\s*x)?/g)];
  if (!matches || matches.length === 0) {
    return { html: '', activeValue: '' };
  }

  const match = matches[0];
  const vMin = parseFloat(match[1]);
  const vMax = parseFloat(match[2]);
  const suffix = match[3] || '';
  const isInt = Number.isInteger(vMin) && Number.isInteger(vMax);

  let activeValStr = '';
  let pillsHTML = '<div class="partner-rank-breakdown" style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;">';

  for (let r = 0; r <= 4; r++) {
    let val = r === 0 ? vMin : r === 4 ? vMax : vMin + (vMax - vMin) * (r / 4.0);
    let valFormatted = isInt ? Math.round(val) + suffix : val.toFixed(1) + suffix;

    const isActive = (r === activeRankIndex);
    if (isActive) {
      activeValStr = valFormatted;
    }

    const starLabel = r === 0 ? '0★ (Base)' : `${r}★`;
    const activeStyle = isActive
      ? 'background:rgba(192, 132, 252, 0.25); border:1px solid #c084fc; color:#fff; font-weight:700;'
      : 'background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); color:var(--text-muted);';

    pillsHTML += `<span class="partner-rank-pill" style="padding:3px 8px; border-radius:6px; font-size:0.78rem; ${activeStyle}">${starLabel}: ${valFormatted}${isActive ? ' ✨' : ''}</span>`;
  }

  pillsHTML += '</div>';

  return {
    html: pillsHTML,
    activeValue: activeValStr
  };
}

function getPartnerSkillInfo(pal) {
  const db = window.PARTNER_SKILLS_DB || {};
  const palName = pal.name || '';
  const info = db[palName] || db[palName.replace(/ (Ignis|Botan|Cryst|Noct|Terra|Lux|Primo)$/, '')] || {
    name: `${palName}'s Partner Ability`,
    desc: `Enhances ${palName}'s combat performance and special ability.`
  };

  let rankIndex = 0;
  if (pal.stars === '★★★★') rankIndex = 4;
  else if (pal.stars === '★★★') rankIndex = 3;
  else if (pal.stars === '★★') rankIndex = 2;
  else if (pal.stars === '★') rankIndex = 1;

  const desc = info.desc || '';
  const breakdown = formatPartnerSkillRankBreakdown(desc, rankIndex);

  return {
    name: info.name,
    desc: desc,
    rank: rankIndex + 1,
    rankIndex: rankIndex,
    rankBreakdownHTML: breakdown.html,
    activeValue: breakdown.activeValue
  };
}

function filterAndSortPals() {
  const query = document.getElementById('searchInput').value.toLowerCase().trim();
  const elemFilter = document.getElementById('elemFilter').value;
  const locFilter = document.getElementById('locationFilter').value;
  const rankFilter = document.getElementById('rankFilter').value;
  const sortOption = document.getElementById('sortSelect').value;

  let filtered = allPals.filter(pal => {
    if (query) {
      const matchName = (pal.name || '').toLowerCase().includes(query);
      const matchNum = (pal.paldeck_num || '').toLowerCase().includes(query);
      const matchId = (pal.raw_id || '').toLowerCase().includes(query);
      const matchGuid = (pal.instance_guid || '').toLowerCase().includes(query);
      const matchSkill = (pal.passive_skills || []).some(p => p.name && p.name.toLowerCase().includes(query));
      if (!matchName && !matchNum && !matchId && !matchGuid && !matchSkill) return false;
    }

    if (elemFilter) {
      const hasElem1 = pal.element1 && pal.element1.toLowerCase() === elemFilter.toLowerCase();
      const hasElem2 = pal.element2 && pal.element2.toLowerCase() === elemFilter.toLowerCase();
      if (!hasElem1 && !hasElem2) return false;
    }

    if (locFilter) {
      if (!pal.location || !pal.location.toLowerCase().includes(locFilter.toLowerCase())) return false;
    }

    if (rankFilter) {
      if (pal.stars !== rankFilter) return false;
    }

    return true;
  });

  filtered.sort((a, b) => {
    if (sortOption === 'level_desc') {
      return (b.level || 0) - (a.level || 0);
    }
    if (sortOption === 'stars_desc') {
      const starsRank = (s) => s === '★★★★' ? 4 : s === '★★★' ? 3 : s === '★★' ? 2 : s === '★' ? 1 : 0;
      return starsRank(b.stars) - starsRank(a.stars);
    }
    if (sortOption === 'name_asc') {
      return (a.name || '').localeCompare(b.name || '');
    }
    if (sortOption === 'location_asc') {
      const locA = a.location || 'Palbox Storage';
      const locB = b.location || 'Palbox Storage';
      return locA.localeCompare(locB);
    }
    const numA = parseInt((a.paldeck_num || '').replace('#', '')) || 9999;
    const numB = parseInt((b.paldeck_num || '').replace('#', '')) || 9999;
    return numA - numB;
  });

  return filtered;
}

function renderMainView() {
  if (currentMainView === 'synergy_teams') {
    renderSynergyTeamsView();
  } else if (currentViewMode === 'list') {
    renderListView();
  } else {
    renderGrid();
  }
}

function renderGrid() {
  const gridContainer = document.getElementById('palGrid');
  const filtered = filterAndSortPals();

  document.getElementById('visibleCount').textContent = filtered.length;

  if (filtered.length === 0) {
    gridContainer.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 64px; color: var(--text-muted);">
        <h3>No Pals match your filters</h3>
        <p style="margin-top: 8px;">Try clearing your search or filter settings.</p>
      </div>
    `;
    return;
  }

  const renderLimit = 150;
  const palsToRender = filtered.slice(0, renderLimit);

  gridContainer.style.display = 'grid';
  gridContainer.innerHTML = palsToRender.map(pal => createPalCardHTML(pal)).join('');
}

function renderListView() {
  const gridContainer = document.getElementById('palGrid');
  const filtered = filterAndSortPals();

  document.getElementById('visibleCount').textContent = filtered.length;

  if (filtered.length === 0) {
    gridContainer.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 64px; color: var(--text-muted);">
        <h3>No Pals match your filters</h3>
      </div>
    `;
    return;
  }

  const renderLimit = 150;
  const palsToRender = filtered.slice(0, renderLimit);

  gridContainer.style.display = 'block';
  gridContainer.innerHTML = `
    <div class="pal-table-container">
      <table class="pal-list-table">
        <thead>
          <tr>
            <th>Paldeck #</th>
            <th>Pal</th>
            <th>Type</th>
            <th class="col-level-rank">Lv / Rank</th>
            <th>Gender</th>
            <th>Work Suitabilities</th>
            <th>Passive Skills (2x2)</th>
            <th>Location</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${palsToRender.map(pal => createPalTableRowHTML(pal)).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderSynergyTeamsView() {
  const gridContainer = document.getElementById('palGrid');
  const teams = getSynergyTeamsData();

  document.getElementById('visibleCount').textContent = teams.length;

  if (teams.length === 0) {
    gridContainer.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 64px; color: var(--text-muted);">
        <h3>No Combat Synergy Teams found</h3>
      </div>
    `;
    return;
  }

  gridContainer.style.display = 'block';

  if (currentViewMode === 'list') {
    gridContainer.innerHTML = `
      <div class="synergy-teams-container">
        ${teams.map(team => createSynergyTeamListTableHTML(team)).join('')}
      </div>
    `;
  } else {
    gridContainer.innerHTML = `
      <div class="synergy-teams-container">
        ${teams.map(team => createSynergyTeamCardHTML(team)).join('')}
      </div>
    `;
  }
}

function getPalPortraitURL(pal) {
  if (pal.portrait_url && pal.portrait_url.includes('Images/')) {
    return pal.portrait_url;
  }

  let nameSlug = (pal.name || '').toLowerCase().replace(/ /g, '-').replace(/['.]/g, '');
  let cleanId = (pal.raw_id || '').replace(/BOSS_|Raid_|NPC_|SUMMON_/g, '').toLowerCase();
  let cleanIdDash = cleanId.replace(/_/g, '-');

  const slugMap = {
    'astralyn': 'astralym.png',
    'lilyqueen-noct': 'lyleen-noct.png',
    'worldtreedragon': 'astralym.png',
    'lilyqueen_dark': 'lyleen-noct.png'
  };

  let target = slugMap[nameSlug] || slugMap[cleanId] || slugMap[cleanIdDash] || `${nameSlug}.png`;
  return `Images/Everything Else/Palworld Complete Palpedia List/${target}`;
}

function createPalCardHTML(pal, showPartnerSkill = false) {
  const portraitSrc = getPalPortraitURL(pal);
  const palName = pal.name || 'Unknown Pal';
  const palGgURL = getPalworldGgURL(palName);
  const palGuid = pal.instance_guid || pal.name || '';
  const safeGuid = palGuid.replace(/'/g, "\\'");

  const portraitHTML = `<img class="portrait-img" src="${portraitSrc}" alt="${palName}" onerror="if(!this.dataset.triedRemote && '${pal.portrait_url || ''}'.startsWith('http')){ this.dataset.triedRemote='true'; this.src='${pal.portrait_url}'; } else { this.outerHTML='<span class=\\'portrait-fallback\\'>🐾</span>'; }">`;
  const portraitWrappedHTML = `<a href="${palGgURL}" target="_blank" rel="noopener" class="portrait-link" title="View ${palName} on Palworld.gg">${portraitHTML}</a>`;

  const paldeckNum = pal.paldeck_num || '#???';
  const starDisplay = pal.stars || '-';

  const alphaIconHTML = pal.is_boss 
    ? `<img class="alpha-badge-icon" src="Images/Icons/PalWorld/Misc/PNG/Alpha_Pals_icon.png" alt="Alpha Pal" title="Alpha Pal (Boss)">`
    : '';

  const palLevel = pal.level ? `Lv. ${pal.level}` : 'Lv. ?';

  let genderHTML = '<span class="gender-pill gender-unknown">⚪ N/A</span>';
  if (pal.gender === 'male') {
    genderHTML = `<span class="gender-pill gender-male"><svg class="svg-icon" viewBox="0 0 24 24"><path fill="#60a5fa" d="M20 4v6h-2V7.41l-3.96 3.97a6 6 0 1 1-1.41-1.41L16.59 6H14V4h6zM10 18a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"/></svg> Male</span>`;
  } else if (pal.gender === 'female') {
    genderHTML = `<span class="gender-pill gender-female"><svg class="svg-icon" viewBox="0 0 24 24"><path fill="#f472b6" d="M12 2a6 6 0 0 0-5 9.33V14H5v2h2v2H5v2h2v2h2v-2h2v-2H9v-2.67A6 6 0 0 0 12 2zm0 10a4 4 0 1 1 0-8 4 4 0 0 1 0 8z"/></svg> Female</span>`;
  }

  const passives = [...(pal.passive_skills || [])];
  while (passives.length < 4) {
    passives.push({ name: '-', tier: 0 });
  }

  const passivesHTML = passives.slice(0, 4).map(p => {
    if (!p.name || p.name === '-') {
      return `<div class="passive-pill passive-empty">-</div>`;
    }
    let tierClass = 'passive-tier-0';
    if (p.tier >= 3) tierClass = 'passive-tier-3';
    else if (p.tier === 2) tierClass = 'passive-tier-2';
    else if (p.tier === 1) tierClass = 'passive-tier-1';
    else if (p.tier < 0) tierClass = 'passive-tier-neg';

    const tooltipHTML = getPassiveTooltipHTML(p.name);
    return `<div class="passive-pill ${tierClass} ${tooltipHTML ? 'has-tooltip' : ''}">${p.name}${tooltipHTML}</div>`;
  }).join('');

  const workBadgesHTML = (pal.work_suitabilities || []).map(w => {
    const iconImg = getWorkIconHTML(w.emoji);
    const fullName = getWorkFullName(w.emoji);
    return `
      <span class="work-badge has-tooltip">
        ${iconImg} ${w.level}
        <div class="tooltip-popup">
          <span class="tooltip-title">${fullName}</span>
          <span class="tooltip-effect">Level ${w.level}</span>
        </div>
      </span>`;
  }).join('') || `<span class="work-badge" style="color: var(--text-dim);">-</span>`;

  const locSvg = getLocationSvg(pal.location);
  const locationHTML = pal.location || 'Palbox Storage';
  const locTooltipHTML = getLocationTooltipHTML(pal.location);

  const elem1Class = getElementBadgeClass(pal.element1);
  const elem1Icon = getElementIconHTML(pal.element1);
  const elem1Tooltip = getElementTooltipHTML(pal.element1);
  let typeHTML = `<span class="elem-badge ${elem1Class} has-tooltip">${elem1Icon}${elem1Tooltip}</span>`;
  if (pal.element2) {
    const elem2Class = getElementBadgeClass(pal.element2);
    const elem2Icon = getElementIconHTML(pal.element2);
    const elem2Tooltip = getElementTooltipHTML(pal.element2);
    typeHTML += ` <span class="elem-badge ${elem2Class} has-tooltip">${elem2Icon}${elem2Tooltip}</span>`;
  }

  const rankTooltipHTML = getRankTooltipHTML(starDisplay);

  let partnerSkillHTML = '';
  if (showPartnerSkill) {
    const partnerInfo = getPartnerSkillInfo(pal);
    partnerSkillHTML = `
      <div class="partner-skill-badge">
        <div class="partner-skill-header">
          <span>⚡ ${partnerInfo.name}</span>
          <span class="partner-rank-tag">Rank ${partnerInfo.rank}</span>
        </div>
        <div class="partner-skill-desc">${partnerInfo.desc}</div>
      </div>
    `;
  }

  return `
    <div class="pal-card" data-guid="${palGuid}" onclick="handlePalCardClick(event, '${safeGuid}')">
      <div class="card-top-bar">
        <div class="top-bar-left">
          <span class="badge-paldeck has-tooltip">${paldeckNum}<div class="tooltip-popup"><span class="tooltip-title">Paldeck #${paldeckNum}</span></div></span>
          <span class="badge-rank has-tooltip">${starDisplay}${rankTooltipHTML}</span>
          ${alphaIconHTML}
        </div>
        <div class="card-type-group">
          ${typeHTML}
          ${pal.instance_guid ? `<button class="card-edit-btn" onclick="openEditModal('${pal.instance_guid}')" title="Edit Pal">✏️</button>` : ''}
        </div>
      </div>

      <div class="card-header-body">
        <div class="portrait-container">
          ${portraitWrappedHTML}
        </div>
        <div class="header-info-col">
          <div class="name-gender-row">
            <span class="pal-name">${palName}</span>
            ${genderHTML}
          </div>
          <div class="pal-level">${palLevel}</div>
          <div class="work-badges-row">
            ${workBadgesHTML}
          </div>
          ${partnerSkillHTML}
        </div>
      </div>

      <div class="card-divider"></div>

      <div class="section-title">Passive Skills</div>
      <div class="passives-grid-2x2">
        ${passivesHTML}
      </div>

      <div class="location-bar has-tooltip">
        <div class="location-bar-content">
          ${locSvg}
          <select class="inline-location-select" data-guid="${pal.instance_guid}" onchange="inlineLocationChange(event, '${pal.instance_guid}')" onclick="event.stopPropagation()">
            <option value="Active Party" ${pal.location === 'Active Party' ? 'selected' : ''}>⚔️ Active Party</option>
            <option value="Palbox Storage" ${(!pal.location || pal.location === 'Palbox Storage') ? 'selected' : ''}>📦 Palbox</option>
            <option value="Main Base" ${pal.location === 'Main Base' ? 'selected' : ''}>🏠 Main Base</option>
            <option value="Mining Base" ${pal.location === 'Mining Base' ? 'selected' : ''}>⛏️ Mining Base</option>
            <option value="Ranching Base" ${pal.location === 'Ranching Base' ? 'selected' : ''}>🐑 Ranching Base</option>
            <option value="Breeding Base" ${pal.location === 'Breeding Base' ? 'selected' : ''}>🥚 Breeding Base</option>
            <option value="Oil Base" ${pal.location === 'Oil Base' ? 'selected' : ''}>🛢️ Oil Base</option>
            <option value="Global Palbox" ${pal.location === 'Global Palbox' ? 'selected' : ''}>🌐 Global Palbox</option>
            ${(!['Active Party', 'Palbox Storage', 'Main Base', 'Mining Base', 'Ranching Base', 'Breeding Base', 'Oil Base', 'Global Palbox'].includes(pal.location || 'Palbox Storage')) ? `<option value="${pal.location}" selected>${pal.location}</option>` : ''}
          </select>
        </div>
        ${locTooltipHTML}
      </div>
    </div>
  `;
}

function createPalTableRowHTML(pal, showPartnerSkill = false) {
  const portraitSrc = getPalPortraitURL(pal);
  const paldeckNum = pal.paldeck_num || '#???';
  const starDisplay = pal.stars || '-';
  const palName = pal.name || 'Unknown Pal';
  const palGgURL = getPalworldGgURL(palName);
  const palLevel = pal.level ? `Lv. ${pal.level}` : 'Lv. ?';
  const palGuid = pal.instance_guid || pal.name || '';
  const safeGuid = palGuid.replace(/'/g, "\\'");

  const tablePortraitWrapped = `<a href="${palGgURL}" target="_blank" rel="noopener" class="table-portrait-link" title="View ${palName} on Palworld.gg"><img class="table-portrait-img" src="${portraitSrc}" alt="${palName}" onerror="this.src='https://raw.githubusercontent.com/palworld-modding/icons/main/pals/lamball.png';"></a>`;

  const elem1Class = getElementBadgeClass(pal.element1);
  const elem1Icon = getElementIconHTML(pal.element1);
  const elem1Tooltip = getElementTooltipHTML(pal.element1);
  let typeHTML = `<span class="elem-badge ${elem1Class} has-tooltip">${elem1Icon}${elem1Tooltip}</span>`;
  if (pal.element2) {
    const elem2Class = getElementBadgeClass(pal.element2);
    const elem2Icon = getElementIconHTML(pal.element2);
    const elem2Tooltip = getElementTooltipHTML(pal.element2);
    typeHTML += ` <span class="elem-badge ${elem2Class} has-tooltip">${elem2Icon}${elem2Tooltip}</span>`;
  }

  const rankTooltipHTML = getRankTooltipHTML(starDisplay);

  let genderHTML = '<span class="gender-pill gender-unknown">⚪ N/A</span>';
  if (pal.gender === 'male') genderHTML = `<span class="gender-pill gender-male">♂ Male</span>`;
  else if (pal.gender === 'female') genderHTML = `<span class="gender-pill gender-female">♀ Female</span>`;

  const workBadgesHTML = (pal.work_suitabilities || []).map(w => {
    const iconImg = getWorkIconHTML(w.emoji);
    const fullName = getWorkFullName(w.emoji);
    return `<span class="work-badge has-tooltip">${iconImg} ${w.level}<div class="tooltip-popup"><span class="tooltip-title">${fullName}</span><span class="tooltip-effect">Level ${w.level}</span></div></span>`;
  }).join(' ') || '-';

  const passives = [...(pal.passive_skills || [])];
  while (passives.length < 4) {
    passives.push({ name: '-', tier: 0 });
  }

  const passivesGridHTML = `
    <div class="passives-grid-2x2" style="width: 180px;">
      ${passives.slice(0, 4).map(p => {
        if (!p.name || p.name === '-') return `<div class="passive-pill passive-empty">-</div>`;
        let tierClass = 'passive-tier-0';
        if (p.tier >= 3) tierClass = 'passive-tier-3';
        else if (p.tier === 2) tierClass = 'passive-tier-2';
        else if (p.tier === 1) tierClass = 'passive-tier-1';
        else if (p.tier < 0) tierClass = 'passive-tier-neg';
        const tooltipHTML = getPassiveTooltipHTML(p.name);
        return `<div class="passive-pill ${tierClass} ${tooltipHTML ? 'has-tooltip' : ''}">${p.name}${tooltipHTML}</div>`;
      }).join('')}
    </div>
  `;

  let partnerTdHTML = '';
  if (showPartnerSkill) {
    const partnerInfo = getPartnerSkillInfo(pal);
    partnerTdHTML = `
      <td>
        <div style="font-size:0.8rem; font-weight:700; color:#c084fc;">⚡ ${partnerInfo.name} <span class="partner-rank-tag">Rank ${partnerInfo.rank}</span></div>
        <div style="font-size:0.72rem; color:var(--text-muted); max-width:200px;">${partnerInfo.desc}</div>
      </td>
    `;
  }

  return `
    <tr data-guid="${palGuid}" onclick="handlePalCardClick(event, '${safeGuid}')">
      <td><span class="badge-paldeck has-tooltip">${paldeckNum}<div class="tooltip-popup"><span class="tooltip-title">Paldeck #${paldeckNum}</span></div></span></td>
      <td>
        <div style="display:flex; align-items:center; gap:10px;">
          ${tablePortraitWrapped}
          <div style="display:flex; align-items:center; gap:6px;">
            <strong style="color:var(--text-main);">${palName}</strong>
            ${pal.is_boss ? `<img class="alpha-badge-icon" src="Images/Icons/PalWorld/Misc/PNG/Alpha_Pals_icon.png" alt="Alpha Pal" title="Alpha Pal (Boss)">` : ''}
          </div>
        </div>
      </td>
      <td>${typeHTML}</td>
      <td class="col-level-rank">${palLevel} <span class="badge-rank has-tooltip">${starDisplay}${rankTooltipHTML}</span></td>
      <td>${genderHTML}</td>
      ${showPartnerSkill ? partnerTdHTML : ''}
      <td><div style="display:flex; gap:4px; flex-wrap:wrap;">${workBadgesHTML}</div></td>
      <td>${passivesGridHTML}</td>
      <td>
        <span class="has-tooltip" style="color:var(--text-muted);">
          <select class="inline-location-select-table" data-guid="${pal.instance_guid}" onchange="inlineLocationChange(event, '${pal.instance_guid}')" onclick="event.stopPropagation()">
            <option value="Active Party" ${pal.location === 'Active Party' ? 'selected' : ''}>⚔️ Active Party</option>
            <option value="Palbox Storage" ${(!pal.location || pal.location === 'Palbox Storage') ? 'selected' : ''}>📦 Palbox</option>
            <option value="Main Base" ${pal.location === 'Main Base' ? 'selected' : ''}>🏠 Main Base</option>
            <option value="Mining Base" ${pal.location === 'Mining Base' ? 'selected' : ''}>⛏️ Mining Base</option>
            <option value="Ranching Base" ${pal.location === 'Ranching Base' ? 'selected' : ''}>🐑 Ranching Base</option>
            <option value="Breeding Base" ${pal.location === 'Breeding Base' ? 'selected' : ''}>🥚 Breeding Base</option>
            <option value="Oil Base" ${pal.location === 'Oil Base' ? 'selected' : ''}>🛢️ Oil Base</option>
            <option value="Global Palbox" ${pal.location === 'Global Palbox' ? 'selected' : ''}>🌐 Global Palbox</option>
            ${(!['Active Party', 'Palbox Storage', 'Main Base', 'Mining Base', 'Ranching Base', 'Breeding Base', 'Oil Base', 'Global Palbox'].includes(pal.location || 'Palbox Storage')) ? `<option value="${pal.location}" selected>${pal.location}</option>` : ''}
          </select>
          ${getLocationTooltipHTML(pal.location)}
        </span>
      </td>
      <td>${pal.instance_guid ? `<button class="card-edit-btn" onclick="openEditModal('${pal.instance_guid}')" title="Edit Pal">✏️ Edit</button>` : '-'}</td>
    </tr>
  `;
}

function resolveTeamMemberPal(m, teamType) {
  let matchedPal = null;
  if (m.guid) {
    matchedPal = allPals.find(p => p.instance_guid === m.guid);
  }
  if (!matchedPal && m.name) {
    matchedPal = allPals.find(p => p.name && p.name.toLowerCase() === m.name.toLowerCase());
  }

  if (!matchedPal) {
    matchedPal = {
      name: m.name || 'Custom Pal',
      instance_guid: m.guid || '',
      paldeck_num: '#???',
      level: 50,
      stars: '★★★★',
      element1: teamType,
      passive_skills: [{ name: 'Legend', tier: 3 }, { name: 'Musclehead', tier: 3 }, { name: 'Ferocious', tier: 3 }],
      location: 'Synergy Team Squad'
    };
  }
  return matchedPal;
}

function createSynergyTeamCardHTML(team) {
  const teamId = team.id || team.team_name;
  const teamName = team.team_name || 'Combat Team';
  const teamType = team.type || 'General';
  const members = team.members || [];
  const synergyDesc = team.synergy_desc || 'No synergy breakdown available.';
  const recs = team.recommendations || '';

  const memberCards = members.map(m => {
    const matchedPal = resolveTeamMemberPal(m, teamType);
    return createPalCardHTML(matchedPal, true);
  }).join('');

  return `
    <div class="synergy-team-card">
      <div class="synergy-team-header">
        <div>
          <div class="synergy-team-title">
            <span>⚔️ ${teamName}</span>
            <span class="elem-badge ${getElementBadgeClass(teamType)} has-tooltip" style="font-size:0.85rem; padding:4px 10px;">${getElementIconHTML(teamType)} ${teamType}${getElementTooltipHTML(teamType)}</span>
          </div>
          <div class="synergy-team-desc"><strong>Synergy Breakdown:</strong> ${synergyDesc}</div>
          ${recs ? `<div class="synergy-team-desc" style="color:var(--accent-blue); margin-top:2px;"><strong>Min/Max Note:</strong> ${recs}</div>` : ''}
        </div>
        <button class="card-edit-btn" onclick="openEditTeamModal('${teamId}')" title="Edit Team" style="padding:6px 12px; font-size:0.85rem;">✏️ Edit Team</button>
      </div>
      <div class="synergy-team-members">
        ${memberCards}
      </div>
    </div>
  `;
}

function createSynergyTeamListTableHTML(team) {
  const teamId = team.id || team.team_name;
  const teamName = team.team_name || 'Combat Team';
  const teamType = team.type || 'General';
  const members = team.members || [];
  const synergyDesc = team.synergy_desc || 'No synergy breakdown available.';
  const recs = team.recommendations || '';

  const memberRows = members.map(m => {
    const matchedPal = resolveTeamMemberPal(m, teamType);
    return createPalTableRowHTML(matchedPal, true);
  }).join('');

  return `
    <div class="synergy-team-card" style="margin-bottom: 24px;">
      <div class="synergy-team-header">
        <div>
          <div class="synergy-team-title">
            <span>⚔️ ${teamName}</span>
            <span class="elem-badge ${getElementBadgeClass(teamType)} has-tooltip" style="font-size:0.85rem; padding:4px 10px;">${getElementIconHTML(teamType)} ${teamType}${getElementTooltipHTML(teamType)}</span>
          </div>
          <div class="synergy-team-desc"><strong>Synergy Breakdown:</strong> ${synergyDesc}</div>
          ${recs ? `<div class="synergy-team-desc" style="color:var(--accent-blue); margin-top:2px;"><strong>Min/Max Note:</strong> ${recs}</div>` : ''}
        </div>
        <button class="card-edit-btn" onclick="openEditTeamModal('${teamId}')" title="Edit Team" style="padding:6px 12px; font-size:0.85rem;">✏️ Edit Team</button>
      </div>
      <div class="pal-table-container">
        <table class="pal-list-table">
          <thead>
            <tr>
              <th>Paldeck #</th>
              <th>Pal</th>
              <th>Type</th>
              <th class="col-level-rank">Lv / Rank</th>
              <th>Gender</th>
              <th>Partner Skill & Rank</th>
              <th>Work Suitabilities</th>
              <th>Passive Skills (2x2)</th>
              <th>Location</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${memberRows}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

/* ==========================================================================
   COMBAT TEAM CREATION & EDITING MODAL CONTROLLERS
   ========================================================================== */

function openAddTeamModal() {
  document.getElementById('teamModalTitle').textContent = '➕ Add New Combat Team';
  document.getElementById('editTeamId').value = '';
  document.getElementById('editTeamName').value = '';
  document.getElementById('editTeamType').value = 'Ground';
  document.getElementById('editSynergyDesc').value = '';
  document.getElementById('editTeamRecs').value = '';

  const palOptions = `<option value="">-- Empty Slot --</option>` + allPals.map(p => {
    const guidTag = p.instance_guid ? ` [GUID: ${p.instance_guid.slice(0,8)}...]` : '';
    return `<option value="${p.instance_guid || p.name}">${p.name} (Lv. ${p.level || 1} ${p.stars || '-'}) ${guidTag}</option>`;
  }).join('');

  for (let i = 0; i < 5; i++) {
    const select = document.getElementById(`team_member_${i}_select`);
    if (select) {
      select.innerHTML = palOptions;
      select.value = '';
    }
  }

  document.getElementById('deleteTeamBtn').style.display = 'none';
  document.getElementById('teamModal').style.display = 'flex';
}

function openEditTeamModal(teamId) {
  const teams = getSynergyTeamsData();
  const team = teams.find(t => t.id === teamId || t.team_name === teamId);
  if (!team) return;

  document.getElementById('teamModalTitle').textContent = `✏️ Edit ${team.team_name}`;
  document.getElementById('editTeamId').value = team.id || team.team_name;
  document.getElementById('editTeamName').value = team.team_name || '';
  document.getElementById('editTeamType').value = team.type || 'Ground';
  document.getElementById('editSynergyDesc').value = team.synergy_desc || '';
  document.getElementById('editTeamRecs').value = team.recommendations || '';

  const palOptions = `<option value="">-- Empty Slot --</option>` + allPals.map(p => {
    const guidTag = p.instance_guid ? ` [GUID: ${p.instance_guid.slice(0,8)}...]` : '';
    return `<option value="${p.instance_guid || p.name}">${p.name} (Lv. ${p.level || 1} ${p.stars || '-'}) ${guidTag}</option>`;
  }).join('');

  const members = team.members || [];
  for (let i = 0; i < 5; i++) {
    const select = document.getElementById(`team_member_${i}_select`);
    if (select) {
      select.innerHTML = palOptions;
      const m = members[i] || {};
      const targetVal = m.guid || m.name || '';
      if (targetVal) {
        select.value = targetVal;
        if (!select.value && m.name) {
          const matchPal = allPals.find(p => p.name.toLowerCase() === m.name.toLowerCase());
          if (matchPal) select.value = matchPal.instance_guid || matchPal.name;
        }
      }
    }
  }

  document.getElementById('deleteTeamBtn').style.display = 'inline-block';
  document.getElementById('teamModal').style.display = 'flex';
}

function closeTeamModal() {
  document.getElementById('teamModal').style.display = 'none';
}

function saveTeamFromModal(e) {
  e.preventDefault();

  const teamId = document.getElementById('editTeamId').value;
  const teamName = document.getElementById('editTeamName').value.trim();
  const teamType = document.getElementById('editTeamType').value;
  const synergyDesc = document.getElementById('editSynergyDesc').value.trim();
  const recs = document.getElementById('editTeamRecs').value.trim();

  const newMembers = [];
  for (let i = 0; i < 5; i++) {
    const select = document.getElementById(`team_member_${i}_select`);
    if (select && select.value) {
      const val = select.value;
      const palMatch = allPals.find(p => p.instance_guid === val || p.name === val);
      if (palMatch) {
        newMembers.push({
          name: palMatch.name,
          guid: palMatch.instance_guid || ''
        });
      } else {
        newMembers.push({
          name: val,
          guid: ''
        });
      }
    }
  }

  const teams = getSynergyTeamsData();

  if (teamId) {
    const teamIndex = teams.findIndex(t => t.id === teamId || t.team_name === teamId);
    if (teamIndex !== -1) {
      teams[teamIndex] = {
        ...teams[teamIndex],
        team_name: teamName,
        type: teamType,
        synergy_desc: synergyDesc,
        recommendations: recs,
        members: newMembers
      };
    }
  } else {
    const newTeamId = 'team-' + Date.now();
    const newTeam = {
      id: newTeamId,
      team_name: teamName,
      type: teamType,
      synergy_desc: synergyDesc,
      recommendations: recs,
      members: newMembers
    };
    teams.unshift(newTeam);
  }

  saveTeamsState(teams);
  closeTeamModal();
  renderMainView();
}

function deleteTeamFromModal() {
  const teamId = document.getElementById('editTeamId').value;
  if (!teamId) return;

  if (confirm('Are you sure you want to delete this Combat Team?')) {
    let teams = getSynergyTeamsData();
    teams = teams.filter(t => (t.id || t.team_name) !== teamId);
    saveTeamsState(teams);
    closeTeamModal();
    renderMainView();
  }
}

/* ==========================================================================
   PAL CREATION & EDITING MODAL CONTROLLERS
   ========================================================================== */

function renderWorkSuitabilityForm(currentSuitabilities = []) {
  const container = document.getElementById('workSuitContainer');
  if (!container) return;

  const currentMap = {};
  currentSuitabilities.forEach(w => {
    WORK_TYPES.forEach(wt => {
      if (w.emoji === wt.emoji || (w.name && w.name.includes(wt.name))) {
        currentMap[wt.name] = parseInt(w.level) || 1;
      }
    });
  });

  container.innerHTML = WORK_TYPES.map(wt => {
    const val = currentMap[wt.name] || 0;
    return `
      <div class="work-suit-edit-item">
        <span>${wt.emoji} ${wt.name}</span>
        <select data-work-name="${wt.name}" data-work-emoji="${wt.emoji}">
          <option value="0" ${val === 0 ? 'selected' : ''}>None</option>
          <option value="1" ${val === 1 ? 'selected' : ''}>Lv 1</option>
          <option value="2" ${val === 2 ? 'selected' : ''}>Lv 2</option>
          <option value="3" ${val === 3 ? 'selected' : ''}>Lv 3</option>
          <option value="4" ${val === 4 ? 'selected' : ''}>Lv 4</option>
          <option value="5" ${val === 5 ? 'selected' : ''}>Lv 5 (Max)</option>
        </select>
      </div>
    `;
  }).join('');
}

function openAddModal() {
  document.getElementById('modalTitle').textContent = '➕ Add New Pal';
  document.getElementById('editInstanceGuid').value = '';
  document.getElementById('editName').value = '';
  document.getElementById('editPaldeckNum').value = '#';
  document.getElementById('editLevel').value = 1;
  document.getElementById('editGender').value = 'male';
  document.getElementById('editLocation').value = 'Palbox Storage';
  document.getElementById('editStars').value = '-';
  document.getElementById('editIsBoss').checked = false;

  for (let i = 1; i <= 4; i++) {
    document.getElementById(`passive${i}_name`).value = '';
    document.getElementById(`passive${i}_tier`).value = '0';
  }

  renderWorkSuitabilityForm([]);
  document.getElementById('deletePalBtn').style.display = 'none';
  document.getElementById('palModal').style.display = 'flex';
}

function openEditModal(instanceGuid) {
  const pal = allPals.find(p => p.instance_guid === instanceGuid || p.name === instanceGuid);
  if (!pal) return;

  document.getElementById('modalTitle').textContent = `✏️ Edit ${pal.name}`;
  document.getElementById('editInstanceGuid').value = pal.instance_guid;
  document.getElementById('editName').value = pal.name || '';
  document.getElementById('editPaldeckNum').value = pal.paldeck_num || '#';
  document.getElementById('editLevel').value = pal.level || 1;
  document.getElementById('editGender').value = pal.gender || 'unknown';
  document.getElementById('editLocation').value = pal.location || 'Palbox Storage';
  document.getElementById('editStars').value = pal.stars || '-';
  document.getElementById('editIsBoss').checked = !!pal.is_boss;

  const passives = pal.passive_skills || [];
  for (let i = 1; i <= 4; i++) {
    const p = passives[i - 1] || {};
    document.getElementById(`passive${i}_name`).value = p.name && p.name !== '-' ? p.name : '';
    document.getElementById(`passive${i}_tier`).value = p.tier !== undefined ? p.tier.toString() : '0';
  }

  renderWorkSuitabilityForm(pal.work_suitabilities || []);
  document.getElementById('deletePalBtn').style.display = 'inline-block';
  document.getElementById('palModal').style.display = 'flex';
}

function closeModal() {
  document.getElementById('palModal').style.display = 'none';
}

function savePalFromModal(e) {
  e.preventDefault();

  const guid = document.getElementById('editInstanceGuid').value;
  const name = document.getElementById('editName').value.trim();
  const paldeckNum = document.getElementById('editPaldeckNum').value.trim();
  const level = parseInt(document.getElementById('editLevel').value) || 1;
  const gender = document.getElementById('editGender').value;
  const location = document.getElementById('editLocation').value;
  const stars = document.getElementById('editStars').value;
  const isBoss = document.getElementById('editIsBoss').checked;

  const passiveSkills = [];
  for (let i = 1; i <= 4; i++) {
    const pName = document.getElementById(`passive${i}_name`).value.trim();
    const pTier = parseInt(document.getElementById(`passive${i}_tier`).value) || 0;
    if (pName) {
      passiveSkills.push({ name: pName, tier: pTier });
    }
  }

  const workSuitabilities = [];
  const suitSelects = document.querySelectorAll('#workSuitContainer select');
  suitSelects.forEach(select => {
    const lvl = parseInt(select.value) || 0;
    if (lvl > 0) {
      const emoji = select.getAttribute('data-work-emoji');
      workSuitabilities.push({ emoji: emoji, level: lvl });
    }
  });

  if (guid) {
    const palIndex = allPals.findIndex(p => p.instance_guid === guid || p.name === guid);
    if (palIndex !== -1) {
      allPals[palIndex] = {
        ...allPals[palIndex],
        name: name,
        paldeck_num: paldeckNum,
        level: level,
        gender: gender,
        location: location,
        stars: stars,
        is_boss: isBoss,
        passive_skills: passiveSkills,
        work_suitabilities: workSuitabilities
      };
    }
  } else {
    const newGuid = 'custom-' + Date.now();
    const newPal = {
      instance_guid: newGuid,
      name: name,
      paldeck_num: paldeckNum,
      level: level,
      gender: gender,
      location: location,
      stars: stars,
      is_boss: isBoss,
      is_imported: true,
      passive_skills: passiveSkills,
      work_suitabilities: workSuitabilities,
      element1: 'Neutral'
    };
    allPals.unshift(newPal);
  }

  savePalsState();
  closeModal();
  renderMainView();
  document.getElementById('totalCount').textContent = allPals.length;
}

function deletePalFromModal() {
  const guid = document.getElementById('editInstanceGuid').value;
  if (!guid) return;

  if (confirm('Are you sure you want to delete this Pal?')) {
    allPals = allPals.filter(p => p.instance_guid !== guid && p.name !== guid);
    savePalsState();
    closeModal();
    renderMainView();
    document.getElementById('totalCount').textContent = allPals.length;
  }
}

// ----------------------------------------------------
// INLINE LOCATION EDIT & AUTO-SYNC
// ----------------------------------------------------
async function inlineLocationChange(event, guid) {
  const newLocation = event.target.value;
  const palIndex = allPals.findIndex(p => p.instance_guid === guid);
  
  if (palIndex > -1) {
    allPals[palIndex].location = newLocation;
    savePalsState();
    // Only re-render the specific card/row if possible, but for simplicity re-render all to apply SVG and sorting
    renderMainView();
    
    // Auto-sync and push to Git
    const syncBtn = document.getElementById('syncPalsBtn');
    if (syncBtn) syncBtn.innerHTML = '🔄 Syncing...';
    
    try {
      const response = await fetch('/api/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(allPals)
      });
      const data = await response.json();
      if (data.status === 'success') {
        if (syncBtn) syncBtn.innerHTML = '✅ Synced & Pushed!';
        setTimeout(() => { if (syncBtn) syncBtn.innerHTML = '☁️ Sync to My Pals'; }, 2000);
      } else {
        console.error("Auto-sync failed:", data.message);
        if (syncBtn) syncBtn.innerHTML = '⚠️ Sync Failed';
      }
    } catch (e) {
      console.error('Error during auto-sync:', e);
      if (syncBtn) syncBtn.innerHTML = '⚠️ Network Error';
    }
  }
}


