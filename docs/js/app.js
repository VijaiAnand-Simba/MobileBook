// Global state
let compatibilityData = null;
let newDevicesData = null;
let currentFilters = {
    os: 'all',
    product: 'all',
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
        
        // Load compatibility data
        console.log('📥 Fetching compatibility data from: compatibility.json');
        const compatResponse = await fetch('compatibility.json');
        
        console.log('📡 Response status:', compatResponse.status, compatResponse.statusText);
        
        if (!compatResponse.ok) {
            throw new Error(`HTTP ${compatResponse.status}: Could not load compatibility.json`);
        }
        
        compatibilityData = await compatResponse.json();
        console.log('✅ Compatibility data loaded:', compatibilityData);
        
        // Check structure
        if (!compatibilityData.products) {
            throw new Error('Invalid JSON structure: missing "products" key');
        }
        
        console.log('📊 Data structure check:', {
            hasProducts: !!compatibilityData.products,
            hasE3: !!compatibilityData.products.E3,
            has365: !!compatibilityData.products['365'],
            hasNOW: !!compatibilityData.products.NOW
        });
        
        // Load new devices data
        console.log('📥 Fetching new devices data from: new_devices.json');
        const newDevicesResponse = await fetch('new_devices.json');
        
        if (newDevicesResponse.ok) {
            newDevicesData = await newDevicesResponse.json();
            console.log('✅ New devices data loaded:', newDevicesData);
        } else {
            console.warn('⚠️ New devices data not found, using empty array');
            newDevicesData = { last_updated: new Date().toISOString(), devices: [] };
        }
        
        // Update UI
        console.log('🎨 Updating UI...');
        updateLastUpdated();
        updateCounts();
        renderCompatibleDevices();
        renderNewDevices();
        
        // Hide loading
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
    
    // Search input
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
    
    // OS filters
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
    
    // Product filters
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
    
    // NEW STRUCTURE: Iterate through products -> E3/365/NOW -> ios/android
    const products = compatibilityData.products;
    
    // Collect devices based on filters
    for (const [productName, productData] of Object.entries(products)) {
        // Filter by product (E3, 365, NOW)
        if (currentFilters.product !== 'all' && currentFilters.product !== productName) {
            continue;
        }
        
        // Iterate through OS types
        for (const [osType, deviceList] of Object.entries(productData)) {
            // Filter by OS
            if (currentFilters.os !== 'all' && currentFilters.os !== osType) {
                continue;
            }
            
            // Add devices
            deviceList.forEach(device => {
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
    if (currentFilters.search) {
        devices = devices.filter(device => 
            device.name?.toLowerCase().includes(currentFilters.search) ||
            device.manufacturer?.toLowerCase().includes(currentFilters.search) ||
            device.model?.toLowerCase().includes(currentFilters.search)
        );
        console.log(`🔍 ${devices.length} devices after search: "${currentFilters.search}"`);
    }
    
    // Group devices by name
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
                os_version: device.os_version || '0',
                rationally_qualified: device.rationally_qualified || false,
                products: new Set()
            };
        }
        grouped[key].products.add(device.product);
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
    
    return `
        <div class="device-card ${rqClass}">
            <div class="device-header">
                <div>
                    <span class="manufacturer-badge">
                        <i class="${manufacturerIcon}"></i>
                        ${device.manufacturer || 'Unknown'}
                    </span>
                    <h3 class="device-name">${device.name}</h3>
                    ${device.model_number ? `<div class="model-number">${device.model_number}</div>` : ''}
                </div>
                <span class="os-badge ${osClass}">
                    <i class="${osIcon}"></i>
                    ${device.os === 'android' ? 'Android' : 'iOS'}
                </span>
            </div>
            
            <div class="device-details">
                <div class="detail-item">
                    <i class="fas fa-mobile-alt"></i>
                    <span>${device.os === 'android' ? 'Android' : 'iOS'} ${device.os_version}+</span>
                </div>
                ${device.model && device.model !== device.name ? `
                <div class="detail-item">
                    <i class="fas fa-tag"></i>
                    <span>${device.model}</span>
                </div>
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
                    <span>Rationally Qualified</span>
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
    
    const devices = newDevicesData.devices || [];
    console.log(`📱 Rendering ${devices.length} new devices`);
    
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
                    <i class="fas fa-code-branch"></i>
                    OS: ${device.os} ${device.os_version}
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
            day: 'numeric'
        });
    } catch (e) {
        lastUpdatedEl.textContent = 'Unknown';
    }
}

function updateCounts() {
    if (!compatibilityData || !compatibilityData.products) return;
    
    // Count unique devices across all products
    const allDevices = new Set();
    
    for (const productData of Object.values(compatibilityData.products)) {
        for (const deviceList of Object.values(productData)) {
            deviceList.forEach(device => allDevices.add(device.name));
        }
    }
    
    const compatibleCountEl = document.getElementById('compatibleCount');
    const newDevicesCountEl = document.getElementById('newDevicesCount');
    
    if (compatibleCountEl) {
        compatibleCountEl.textContent = allDevices.size;
        console.log(`📊 Compatible devices count: ${allDevices.size}`);
    }
    
    if (newDevicesCountEl && newDevicesData) {
        newDevicesCountEl.textContent = newDevicesData.devices.length;
        console.log(`📊 New devices count: ${newDevicesData.devices.length}`);
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
            </div>
        `;
        loading.style.display = 'block';
    }
}
