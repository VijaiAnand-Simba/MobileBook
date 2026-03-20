// Global state
let compatibilityData = null;
let newDevicesData = null;
let searchEngine = null;
let currentFilters = {
    os: 'all',
    product: 'all',
    region: 'all',
    search: ''
};

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 App starting...');
    initializeApp();
    setupEventListeners();
});

async function initializeApp() {
    try {
        showLoading(true);
        
        console.log('📥 Fetching compatibility data from: compatibility.json');
        const compatResponse = await fetch('compatibility.json');
        
        console.log('📡 Response status:', compatResponse.status, compatResponse.statusText);
        
        if (!compatResponse.ok) {
            throw new Error(`HTTP ${compatResponse.status}: Could not load compatibility.json`);
        }
        
        compatibilityData = await compatResponse.json();
        console.log('✅ Compatibility data loaded:', compatibilityData);
        
        if (!compatibilityData.products) {
            throw new Error('Invalid JSON structure: missing "products" key');
        }
        
        // Initialize search engine
        searchEngine = new DeviceSearchEngine();
        
        console.log('📥 Fetching new devices data from: new_devices.json');
        const newDevicesResponse = await fetch('new_devices.json');
        
        if (newDevicesResponse.ok) {
            newDevicesData = await newDevicesResponse.json();
            console.log('✅ New devices data loaded:', newDevicesData);
        } else {
            console.warn('⚠️ New devices data not found, using empty array');
            newDevicesData = { last_updated: new Date().toISOString(), devices: [] };
        }
        
        console.log('🎨 Updating UI...');
        updateLastUpdated();
        updateCounts();
        renderCompatibleDevices();
        renderNewDevices();
        
        showLoading(false);
        
        console.log('✅ App initialized successfully!');
        
    } catch (error) {
        console.error('❌ Error loading data:', error);
        showError(`Failed to load device data: ${error.message}`);
        showLoading(false);
    }
}

function showLoading(show) {
    const loading = document.getElementById('loading');
    const searchResults = document.getElementById('searchResults');
    const noResults = document.getElementById('noResults');
    
    if (loading) {
        loading.style.display = show ? 'block' : 'none';
    }
    if (searchResults && !show) {
        searchResults.style.display = 'block';
    }
    if (noResults && show) {
        noResults.style.display = 'none';
    }
}

function setupEventListeners() {
    console.log('🎧 Setting up event listeners...');
    
    const searchInput = document.getElementById('deviceSearch');
    const clearBtn = document.getElementById('clearSearch');
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce((e) => {
            currentFilters.search = e.target.value.toLowerCase();
            if (clearBtn) clearBtn.style.display = e.target.value ? 'block' : 'none';
            console.log('🔍 Search:', currentFilters.search);
            renderCompatibleDevices();
        }, 300));
    }
    
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            currentFilters.search = '';
            clearBtn.style.display = 'none';
            renderCompatibleDevices();
        });
    }
    
    // OS filter
    document.querySelectorAll('[data-filter]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const filter = e.currentTarget.dataset.filter;
            currentFilters.os = filter;
            console.log('📱 OS filter:', filter);
            
            document.querySelectorAll('[data-filter]').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            
            renderCompatibleDevices();
        });
    });
    
    // Product filter
    document.querySelectorAll('[data-product]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const product = e.currentTarget.dataset.product;
            currentFilters.product = product;
            console.log('🏷️ Product filter:', product);
            
            document.querySelectorAll('[data-product]').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            
            renderCompatibleDevices();
        });
    });
    
    // Region filter
    document.querySelectorAll('[data-region]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const region = e.currentTarget.dataset.region;
            currentFilters.region = region;
            console.log('🌍 Region filter:', region);
            
            document.querySelectorAll('[data-region]').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            
            renderCompatibleDevices();
        });
    });
    
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tab = e.currentTarget.dataset.tab;
            console.log('🗂️ Switching to tab:', tab);
            switchTab(tab);
        });
    });
    
    console.log('✅ Event listeners setup complete');
}

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    if (tab === 'compatible') {
        document.getElementById('compatibleTab').classList.add('active');
    } else if (tab === 'new-devices') {
        document.getElementById('newDevicesTab').classList.add('active');
    }
}

function renderCompatibleDevices() {
    console.log('🎨 Rendering compatible devices...');
    
    if (!compatibilityData || !compatibilityData.products) {
        console.warn('⚠️ No compatibility data available yet');
        return;
    }
    
    const resultsContainer = document.getElementById('searchResults');
    const noResults = document.getElementById('noResults');
    
    if (!resultsContainer || !noResults) {
        console.error('❌ Required DOM elements not found');
        return;
    }
    
    let devices = [];
    
    const products = compatibilityData.products;
    
    // Collect all devices
    for (const [productName, productData] of Object.entries(products)) {
        if (currentFilters.product !== 'all' && currentFilters.product !== productName) {
            continue;
        }
        
        for (const [osType, deviceList] of Object.entries(productData)) {
            if (currentFilters.os !== 'all' && currentFilters.os !== osType) {
                continue;
            }
            
            deviceList.forEach(device => {
                // Apply region filter
                if (currentFilters.region !== 'all' && device.region !== currentFilters.region) {
                    return;
                }
                
                devices.push({
                    ...device,
                    os: osType,
                    product: productName
                });
            });
        }
    }
    
    console.log(`📊 Found ${devices.length} devices before search filter`);
    
    // Apply search filter
    if (currentFilters.search && searchEngine) {
        const groupedForSearch = groupDevicesByName(devices);
        searchEngine.buildIndex(groupedForSearch);
        const searchResults = searchEngine.search(currentFilters.search);
        devices = searchResults.flatMap(result => 
            devices.filter(d => d.name === result.name)
        );
        console.log(`🔍 ${devices.length} devices after search: "${currentFilters.search}"`);
    }
    
    const groupedDevices = groupDevicesByName(devices);
    console.log(`📦 ${groupedDevices.length} unique devices after grouping`);
    
    if (groupedDevices.length === 0) {
        resultsContainer.innerHTML = '';
        resultsContainer.style.display = 'none';
        noResults.style.display = 'block';
        console.log('📭 No devices to display');
        return;
    }
    
    noResults.style.display = 'none';
    resultsContainer.style.display = 'grid';
    resultsContainer.innerHTML = groupedDevices.map(device => createDeviceCard(device)).join('');
    console.log(`✅ Rendered ${groupedDevices.length} device cards`);
}

function groupDevicesByName(devices) {
    const grouped = {};
    
    devices.forEach(device => {
        const key = device.name;
        if (!grouped[key]) {
            grouped[key] = {
                name: device.name,
                manufacturer: device.manufacturer || 'Unknown',
                model: device.model || device.name,
                model_number: device.model_number || '',
                os: device.os,
                os_version: device.os_version || '',
                rationally_qualified: device.rationally_qualified || false,
                region: device.region || 'US',
                products: new Set()
            };
        }
        grouped[key].products.add(device.product);
        
        // If device is in both regions, mark it
        if (device.region && device.region !== grouped[key].region) {
            grouped[key].region = 'BOTH';
        }
    });
    
    return Object.values(grouped).map(device => ({
        ...device,
        products: Array.from(device.products)
    }));
}

function createDeviceCard(device) {
    const osIcon = device.os === 'android' ? 'fab fa-android' : 'fab fa-apple';
    const osClass = device.os === 'android' ? 'android' : 'ios';
    const rqClass = device.rationally_qualified ? 'rationally-qualified' : '';
    const manufacturerIcon = getManufacturerIcon(device.manufacturer);
    
    // Region badge
    let regionBadgeHTML = '';
    if (device.region === 'BOTH') {
        regionBadgeHTML = `
            <span class="region-badge us" title="Available in US">US</span>
            <span class="region-badge ous" title="Available Outside US">OUS</span>
        `;
    } else if (device.region === 'OUS') {
        regionBadgeHTML = `<span class="region-badge ous" title="Outside US">OUS</span>`;
    } else if (device.region === 'US') {
        regionBadgeHTML = `<span class="region-badge us" title="United States">US</span>`;
    }
    
    return `
        <div class="device-card ${rqClass}">
            <div class="device-header">
                <div>
                    <span class="manufacturer-badge">
                        <i class="${manufacturerIcon}"></i>
                        ${device.manufacturer || 'Unknown'}
                    </span>
                    <h3 class="device-name">
                        ${device.name}
                        ${device.rationally_qualified ? '<span class="rq-badge">RQ</span>' : ''}
                    </h3>
                    ${device.model_number ? `<div class="model-number">${device.model_number}</div>` : ''}
                </div>
                <div style="display: flex; flex-direction: column; gap: 0.5rem; align-items: flex-end;">
                    <span class="os-badge ${osClass}">
                        <i class="${osIcon}"></i>
                        ${device.os === 'android' ? 'Android' : 'iOS'}
                    </span>
                    <div style="display: flex; gap: 0.25rem;">
                        ${regionBadgeHTML}
                    </div>
                </div>
            </div>
            
            <div class="device-details">
                ${device.model ? `
                    <span class="detail-item">
                        <i class="fas fa-mobile-alt"></i>
                        ${device.model}
                    </span>
                ` : ''}
                ${device.os_version ? `
                    <span class="detail-item">
                        <i class="fas fa-code-branch"></i>
                        v${device.os_version}+
                    </span>
                ` : ''}
            </div>
            
            <div class="compatibility-badges">
                ${device.products.map(product => `
                    <span class="product-badge">
                        <i class="fas fa-check"></i>
                        ${product}
                    </span>
                `).join('')}
            </div>
            
            ${device.rationally_qualified ? `
                <div class="rq-info">
                    <i class="fas fa-info-circle"></i>
                    <span>Rationally Qualified Device</span>
                </div>
            ` : ''}
        </div>
    `;
}

function getManufacturerIcon(manufacturer) {
    const icons = {
        'Apple': 'fab fa-apple',
        'Google': 'fab fa-google',
        'Samsung': 'fab fa-android',
        'Motorola': 'fas fa-mobile-alt',
        'OnePlus': 'fas fa-mobile',
        'LG': 'fas fa-tv',
        'HTC': 'fas fa-mobile-alt',
        'Nokia': 'fas fa-mobile',
        'HMD Global': 'fas fa-mobile',
        'Sony': 'fas fa-mobile-alt',
        'Xiaomi': 'fas fa-mobile',
        'Lively': 'fas fa-mobile'
    };
    
    return icons[manufacturer] || 'fas fa-mobile-alt';
}

// Filter out iPad devices from new devices
function filterOutIPads(devices) {
    const filtered = devices.filter(device => {
        const deviceName = (device.name || '').toLowerCase();
        const deviceModel = (device.model || '').toLowerCase();
        const deviceOS = (device.os || '').toLowerCase();
        
        // Exclude if name, model, or OS contains "ipad"
        const isIPad = deviceName.includes('ipad') || 
                       deviceModel.includes('ipad') || 
                       deviceOS.includes('ipados');
        
        if (isIPad) {
            console.log(`🚫 Filtering out iPad: ${device.name}`);
        }
        
        return !isIPad;
    });
    
    console.log(`📱 Filtered ${devices.length - filtered.length} iPad device(s) from new devices`);
    return filtered;
}

function renderNewDevices() {
    if (!newDevicesData) {
        console.warn('⚠️ No new devices data');
        return;
    }
    
    const container = document.getElementById('newDevicesResults');
    const noDevices = document.getElementById('noNewDevices');
    
    if (!container || !noDevices) {
        console.error('❌ New devices containers not found');
        return;
    }
    
    // Filter out iPad devices
    const allDevices = newDevicesData.devices || [];
    const devices = filterOutIPads(allDevices);
    
    console.log(`📱 Rendering ${devices.length} new devices (${allDevices.length} total, ${allDevices.length - devices.length} iPad(s) filtered)`);
    
    if (devices.length === 0) {
        container.innerHTML = '';
        noDevices.style.display = 'block';
        return;
    }
    
    noDevices.style.display = 'none';
    container.innerHTML = devices.map(device => createNewDeviceCard(device)).join('');
}

function createNewDeviceCard(device) {
    const osIcon = device.os === 'Android' ? 'fab fa-android' : 'fab fa-apple';
    
    return `
        <div class="new-device-card">
            <div class="new-device-header">
                <h3 class="new-device-name">
                    <i class="${osIcon}"></i>
                    ${device.name}
                </h3>
            </div>
            <div class="new-device-info">
                <span>
                    <i class="fas fa-calendar-alt"></i>
                    Released: ${formatDate(device.release_date)}
                </span>
                <span>
                    <i class="fas fa-mobile-alt"></i>
                    OS: ${device.os}
                </span>
                <span style="color: var(--warning-color); font-weight: 600;">
                    <i class="fas fa-exclamation-circle"></i>
                    Not yet in compatibility list
                </span>
            </div>
        </div>
    `;
}

function updateLastUpdated() {
    if (!compatibilityData) return;
    
    const lastUpdatedEl = document.getElementById('lastUpdated');
    if (!lastUpdatedEl) return;
    
    try {
        const lastUpdated = new Date(compatibilityData.last_updated);
        lastUpdatedEl.textContent = lastUpdated.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        lastUpdatedEl.textContent = 'Unknown';
    }
}

function updateCounts() {
    if (!compatibilityData || !compatibilityData.products) return;
    
    const allDevices = new Set();
    let usCount = 0;
    let ousCount = 0;
    
    for (const productData of Object.values(compatibilityData.products)) {
        for (const deviceList of Object.values(productData)) {
            deviceList.forEach(device => {
                allDevices.add(device.name);
                if (device.region === 'US') usCount++;
                else if (device.region === 'OUS') ousCount++;
            });
        }
    }
    
    const compatibleCountEl = document.getElementById('compatibleCount');
    const newDevicesCountEl = document.getElementById('newDevicesCount');
    
    if (compatibleCountEl) {
        compatibleCountEl.textContent = allDevices.size;
        console.log(`📊 Compatible devices count: ${allDevices.size} (US: ${usCount}, OUS: ${ousCount})`);
    }
    
    if (newDevicesCountEl && newDevicesData) {
        // Filter iPads before counting
        const filteredDevices = filterOutIPads(newDevicesData.devices);
        newDevicesCountEl.textContent = filteredDevices.length;
        console.log(`📊 New devices count: ${filteredDevices.length} (${newDevicesData.devices.length} total, ${newDevicesData.devices.length - filteredDevices.length} iPad(s) filtered)`);
    }
}

function formatDate(dateString) {
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    } catch (e) {
        return dateString;
    }
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function showError(message) {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.innerHTML = `
            <div style="color: var(--danger-color); text-align: center; padding: 2rem;">
                <i class="fas fa-exclamation-triangle" style="font-size: 3rem; margin-bottom: 1rem;"></i>
                <h3>${message}</h3>
                <p style="margin-top: 1rem;">Please check the browser console (F12) for more details.</p>
                <p style="margin-top: 0.5rem; color: var(--text-secondary);">
                    Make sure compatibility.json is in the same directory as this page.
                </p>
            </div>
        `;
        loading.style.display = 'block';
    }
}
