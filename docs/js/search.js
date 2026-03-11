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
            device.os_version,
            ...device.products.map(p => p.toLowerCase())
        ];
        
        // Add brand extraction
        const brand = this.extractBrand(device.name);
        if (brand) terms.push(brand.toLowerCase());
        
        return terms;
    }
    
    extractBrand(deviceName) {
        const brands = ['iPhone', 'iPad', 'Samsung', 'Google', 'Pixel', 'OnePlus', 'Xiaomi', 'Huawei', 'LG', 'Motorola', 'Nokia'];
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
        const distance = this.levenshteinDistance(text, pattern);
        return distance <= 2; // Allow 2 character differences
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
                        matrix[i - 1][j - 1] + 1,
                        matrix[i][j - 1] + 1,
                        matrix[i - 1][j] + 1
                    );
                }
            }
        }
        
        return matrix[b.length][a.length];
    }
    
    calculateRelevance(device, query) {
        let score = 0;
        
        // Exact match in name
        if (device.name.toLowerCase().includes(query)) {
            score += 100;
        }
        
        // Starts with query
        if (device.name.toLowerCase().startsWith(query)) {
            score += 50;
        }
        
        // Match in other terms
        device.searchTerms.forEach(term => {
            if (term.includes(query)) {
                score += 10;
            }
        });
        
        return score;
    }
}

// Export for use in app.js
window.DeviceSearchEngine = DeviceSearchEngine;
