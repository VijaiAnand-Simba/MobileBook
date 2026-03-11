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
    initializeApp();
    setupEventListeners();
});

async function initializeApp() {
    try {
        // Load compatibility data
        const compatResponse = await fetch('../data/compatibility.json');
        compatibilityData = await compatResponse.json();
        
        // Load new devices data
        const newDevicesResponse = await fetch('../data/new_devices.json');
        newDevicesData = await newDevicesResponse.json();
        
        // Update UI
        updateLastUpdated();
        renderCompatibleDevices();
        renderNewDevices();
        updateCounts();
        
        // Hide loading
        document.getElementById('loading').style.display = 'none';
        
    } catch (error) {
        console.error('Error loading data:', error);
        showError('Failed to load device data. Please try again later.');
    }
}

function setupEventListeners() {
    // Search input
    const searchInput = document.getElementById('deviceSearch');
    const clearBtn = document.getElementById('clearSearch');
    
    searchInput.addEventListener('input', debounce((e) => {
        currentFilters.search = e.target.value.toLowerCase();
        clearBtn.style.display = e.target.value ? 'block' : 'none';
        renderCompatibleDevices();
    }, 300));
    
    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        currentFilters.search = '';
        clearBtn.style.display = 'none';
        renderCompatibleDevices();
    });
    
    // OS filters
    document.querySelectorAll('[data-filter]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const filter = e.currentTarget.dataset.filter;
            currentFilters.os = filter;
            
            // Update active state
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
            
            // Update active state
            document.querySelectorAll('[data-product]').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            
            renderCompatibleDevices();
        });
    });
    
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tab = e.currentTarget.dataset.tab;
            switchTab(tab);
        });
    });
}

function switchTab(tab) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    
    // Update tab content
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
    if (!compatibilityData) return;
    
    const resultsContainer = document.getElementById('searchResults');
    const noResults = document.getElementById('noResults');
    
    let devices = [];
    
    // Collect devices based on filters
    ['android', 'ios'].forEach(os => {
        if (currentFilters.os === 'all' || currentFilters.os === os) {
            ['E3', '365'].forEach(product => {
                if (currentFilters.product === 'all' || currentFilters.product === product) {
                    const productDevices = compatibilityData[os][product] || [];
                    productDevices.forEach(device => {
                        devices.push({
                            ...device,
                            os,
                            product
                        });
                    });
                }
            });
        }
    });
    
    // Apply search filter
    if (currentFilters.search) {
        devices = devices.filter(device => 
            device.name.toLowerCase().includes(currentFilters.search)
        );
    }
    
    // Remove duplicates and group by device
    const groupedDevices = groupDevicesByName(devices);
    
    if (groupedDevices.length === 0) {
        resultsContainer.innerHTML = '';
        noResults.style.display = 'block';
        return;
    }
    
    noResults.style.display = 'none';
    resultsContainer.innerHTML = groupedDevices.map(device => createDeviceCard(device)).join('');
}

function groupDevicesByName(devices) {
    const grouped = {};
    
    devices.forEach(device => {
        if (!grouped[device.name]) {
            grouped[device.name] = {
                name: device.name,
                os: device.os,
                os_version: device.os_version,
                products: new Set()
            };
        }
        grouped[device.name].products.add(device.product);
    });
    
    return Object.values(grouped).map(device => ({
        ...device,
        products: Array.from(device.products)
    }));
}

function createDeviceCard(device) {
    const osIcon = device.os === 'android' ? 'fab fa-android' : 'fab fa-apple';
    const osClass = device.os === 'android' ? 'android' : 'ios';
    
    return `
        <div class="device-card">
            <div class="device-header">
                <h3 class="device-name">${device.name}</h3>
                <span class="os-badge ${osClass}">
                    <i class="${osIcon}"></i>
                    ${device.os === 'android' ? 'Android' : 'iOS'}
                </span>
            </div>
            
            <div class="device-details">
                <div class="detail-item">
                    <i class="fas fa-mobile-alt"></i>
                    <span>OS Version: ${device.os_version}+</span>
                </div>
            </div>
            
            <div class="compatibility-badges">
                ${device.products.map(product => `
                    <span class="product-badge">
                        <i class="fas fa-check"></i>
                        ${product}
                    </span>
                `).join('')}
            </div>
        </div>
    `;
}

function renderNewDevices() {
    if (!newDevicesData) return;
    
    const container = document.getElementById('newDevicesResults');
    const noDevices = document.getElementById('noNewDevices');
    const devices = newDevicesData.devices || [];
    
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
    
    const lastUpdated = new Date(compatibilityData.last_updated);
    document.getElementById('lastUpdated').textContent = lastUpdated.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function updateCounts() {
    if (!compatibilityData || !newDevicesData) return;
    
    // Count compatible devices
    let compatibleCount = 0;
    ['android', 'ios'].forEach(os => {
        ['E3', '365'].forEach(product => {
            compatibleCount += (compatibilityData[os][product] || []).length;
        });
    });
    
    document.getElementById('compatibleCount').textContent = compatibleCount;
    document.getElementById('newDevicesCount').textContent = newDevicesData.devices.length;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
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
    loading.innerHTML = `
        <div style="color: var(--danger-color);">
            <i class="fas fa-exclamation-triangle" style="font-size: 3rem; margin-bottom: 1rem;"></i>
            <h3>${message}</h3>
        </div>
    `;
}
