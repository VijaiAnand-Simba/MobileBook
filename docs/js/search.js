// Advanced search functionality with fuzzy matching

class DeviceSearchEngine {
    constructor() {
        this.index = [];
    }
    
    buildIndex(devices) {
        this.index = devices.map(device => ({
            ...device,
            searchTerms: this.generateSearchTerms(device)
        }));
    }
    
    generateSearchTerms(device) {
        const terms = [
            device.name.toLowerCase(),
            device.os.toLowerCase(),
            device.manufacturer?.toLowerCase() || '',
            device.model?.toLowerCase() || '',
            device.model_number?.toLowerCase() || '',
            device.os_version || '',
            device.region?.toLowerCase() || '',
            ...device.products.map(p => p.toLowerCase())
        ].filter(Boolean);
        
        // Add brand extraction
        const brand = this.extractBrand(device.name);
        if (brand) terms.push(brand.toLowerCase());
        
        // Add model number variations
        if (device.model_number) {
            terms.push(device.model_number.replace(/[-\s]/g, '').toLowerCase());
        }
        
        return terms;
    }
    
    extractBrand(deviceName) {
        const brands = [
            'iPhone', 'iPad', 'iPod', 'Apple Watch',
            'Samsung', 'Galaxy',
            'Google', 'Pixel',
            'OnePlus', 'Xiaomi', 'Huawei', 'LG', 
            'Motorola', 'Nokia', 'HTC', 'Sony',
            'Oppo', 'Vivo', 'Realme', 'Asus'
        ];
        const found = brands.find(brand => deviceName.includes(brand));
        return found || null;
    }
    
    search(query) {
        if (!query) return this.index;
        
        const queryLower = query.toLowerCase();
        const results = this.index.filter(device => 
            device.searchTerms.some(term => 
                term.includes(queryLower) || this.fuzzyMatch(term, queryLower)
            )
        );
        
        // Sort by relevance
        return results.sort((a, b) => {
            const aScore = this.calculateRelevance(a, queryLower);
            const bScore = this.calculateRelevance(b, queryLower);
            return bScore - aScore;
        });
    }
    
    fuzzyMatch(text, pattern) {
        // Skip fuzzy match for very short queries
        if (pattern.length < 3) return false;
        
        const distance = this.levenshteinDistance(text, pattern);
        const threshold = Math.max(2, Math.floor(pattern.length * 0.2)); // 20% error tolerance
        return distance <= threshold;
    }
    
    levenshteinDistance(a, b) {
        const matrix = [];
        
        for (let i = 0; i <= b.length; i++) {
            matrix[i] = [i];
        }
        
        for (let j = 0; j <= a.length; j++) {
            matrix[0][j] = j;
        }
        
        for (let i = 1; i <= b.length; i++) {
            for (let j = 1; j <= a.length; j++) {
                if (b.charAt(i - 1) === a.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                } else {
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j - 1] + 1, // substitution
                        matrix[i][j - 1] + 1,     // insertion
                        matrix[i - 1][j] + 1      // deletion
                    );
                }
            }
        }
        
        return matrix[b.length][a.length];
    }
    
    calculateRelevance(device, query) {
        let score = 0;
        
        const nameLower = device.name.toLowerCase();
        const manufacturerLower = (device.manufacturer || '').toLowerCase();
        const modelLower = (device.model || '').toLowerCase();
        
        // Exact match in name (highest priority)
        if (nameLower === query) {
            score += 1000;
        }
        
        // Name contains query
        if (nameLower.includes(query)) {
            score += 100;
        }
        
        // Name starts with query
        if (nameLower.startsWith(query)) {
            score += 50;
        }
        
        // Manufacturer match
        if (manufacturerLower === query) {
            score += 75;
        }
        
        if (manufacturerLower.includes(query)) {
            score += 40;
        }
        
        // Model match
        if (modelLower.includes(query)) {
            score += 30;
        }
        
        // Model number match
        if (device.model_number?.toLowerCase().includes(query)) {
            score += 60;
        }
        
        // Region match
        if (device.region?.toLowerCase() === query) {
            score += 20;
        }
        
        // Product match
        if (device.products.some(p => p.toLowerCase().includes(query))) {
            score += 15;
        }
        
        // OS match
        if (device.os.toLowerCase().includes(query)) {
            score += 10;
        }
        
        // Match in other search terms
        device.searchTerms.forEach(term => {
            if (term.includes(query)) {
                score += 5;
            }
        });
        
        return score;
    }
}

// Export for use in app.js
if (typeof window !== 'undefined') {
    window.DeviceSearchEngine = DeviceSearchEngine;
}
