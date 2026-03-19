// Advanced search functionality with fuzzy matching

class DeviceSearchEngine {
    constructor() {
        this.index = [];
    }
    
    buildIndex(devices) {
        this.index = devices.map(device => ({
            ...device,
            searchTerms: this.generateSearchTerms(device),
            tokens: this.tokenize(device)
        }));
    }
    
    tokenize(device) {
        // Break down device info into individual tokens for better matching
        const tokens = {
            brand: this.extractBrand(device.name)?.toLowerCase() || '',
            model: (device.model || '').toLowerCase(),
            modelNumber: (device.model_number || '').toLowerCase(),
            fullName: device.name.toLowerCase(),
            manufacturer: (device.manufacturer || '').toLowerCase(),
            os: device.os.toLowerCase(),
            region: (device.region || '').toLowerCase(),
            products: device.products.map(p => p.toLowerCase())
        };
        
        // Extract numeric model from name (e.g., "5" from "Pixel 5")
        const numericModel = device.name.match(/\b(\d+[\w]*)\b/);
        tokens.numericModel = numericModel ? numericModel[1].toLowerCase() : '';
        
        return tokens;
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
    
    parseQuery(query) {
        // Parse query to identify brand and model separately
        // e.g., "pixel 5" -> {brand: "pixel", model: "5"}
        const queryLower = query.toLowerCase().trim();
        const parts = queryLower.split(/\s+/);
        
        const parsed = {
            full: queryLower,
            parts: parts,
            hasNumber: /\d/.test(queryLower),
            isMultiWord: parts.length > 1
        };
        
        // Try to identify brand + model pattern
        if (parsed.isMultiWord) {
            const brand = this.extractBrand(query);
            if (brand) {
                parsed.brand = brand.toLowerCase();
                // Extract everything after the brand as potential model
                const brandIndex = queryLower.indexOf(brand.toLowerCase());
                const afterBrand = queryLower.substring(brandIndex + brand.length).trim();
                if (afterBrand) {
                    parsed.model = afterBrand;
                }
            }
        }
        
        return parsed;
    }
    
    search(query) {
        if (!query) return this.index;
        
        const parsedQuery = this.parseQuery(query);
        const queryLower = parsedQuery.full;
        
        const results = this.index.filter(device => 
            this.matchesDevice(device, parsedQuery)
        );
        
        // Sort by relevance
        return results.sort((a, b) => {
            const aScore = this.calculateRelevance(a, parsedQuery);
            const bScore = this.calculateRelevance(b, parsedQuery);
            return bScore - aScore;
        });
    }
    
    matchesDevice(device, parsedQuery) {
        const queryLower = parsedQuery.full;
        
        // Exact full name match
        if (device.tokens.fullName === queryLower) {
            return true;
        }
        
        // If query has brand + model (e.g., "pixel 5")
        if (parsedQuery.brand && parsedQuery.model) {
            const deviceBrand = device.tokens.brand;
            const deviceName = device.tokens.fullName;
            
            // Check if device has the same brand
            if (deviceBrand === parsedQuery.brand || deviceName.includes(parsedQuery.brand)) {
                // Check if the model matches with word boundaries
                // This prevents "pixel 5" from matching "pixel 50" or "pixel 5a"
                const modelPattern = new RegExp(`\\b${this.escapeRegex(parsedQuery.model)}\\b`, 'i');
                
                if (modelPattern.test(deviceName) || 
                    modelPattern.test(device.tokens.model) ||
                    modelPattern.test(device.tokens.numericModel)) {
                    return true;
                }
            }
        }
        
        // Check for word boundary matches (prevents partial matches)
        const wordBoundaryPattern = new RegExp(`\\b${this.escapeRegex(queryLower)}\\b`, 'i');
        if (wordBoundaryPattern.test(device.tokens.fullName)) {
            return true;
        }
        
        // Fallback to general matching
        const hasMatch = device.searchTerms.some(term => {
            // For single word queries, use word boundaries
            if (!parsedQuery.isMultiWord) {
                const pattern = new RegExp(`\\b${this.escapeRegex(queryLower)}`, 'i');
                return pattern.test(term);
            }
            // For multi-word, use contains
            return term.includes(queryLower);
        });
        
        if (hasMatch) {
            return true;
        }
        
        // Fuzzy match only if query is long enough and no exact matches found
        if (queryLower.length >= 4) {
            return device.searchTerms.some(term => this.fuzzyMatch(term, queryLower));
        }
        
        return false;
    }
    
    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
    
    fuzzyMatch(text, pattern) {
        // Skip fuzzy match for very short queries
        if (pattern.length < 4) return false;
        
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
    
    calculateRelevance(device, parsedQuery) {
        let score = 0;
        const query = parsedQuery.full;
        
        const nameLower = device.name.toLowerCase();
        const manufacturerLower = (device.manufacturer || '').toLowerCase();
        const modelLower = (device.model || '').toLowerCase();
        
        // Exact full match (highest priority)
        if (nameLower === query) {
            score += 10000;
        }
        
        // Exact match with word boundaries
        const wordBoundaryPattern = new RegExp(`\\b${this.escapeRegex(query)}\\b`, 'i');
        if (wordBoundaryPattern.test(nameLower)) {
            score += 5000;
        }
        
        // Brand + Model exact match (e.g., "pixel 5" matches "Google Pixel 5")
        if (parsedQuery.brand && parsedQuery.model) {
            const hasBrand = nameLower.includes(parsedQuery.brand);
            const modelPattern = new RegExp(`\\b${this.escapeRegex(parsedQuery.model)}\\b`, 'i');
            const hasExactModel = modelPattern.test(nameLower);
            
            if (hasBrand && hasExactModel) {
                score += 8000;
            } else if (hasBrand) {
                score += 50; // Has brand but not exact model
            }
        }
        
        // Name starts with query
        if (nameLower.startsWith(query)) {
            score += 3000;
        }
        
        // Name contains query (but not as substring of another word)
        if (nameLower.includes(query)) {
            score += 100;
        }
        
        // Manufacturer exact match
        if (manufacturerLower === query) {
            score += 2000;
        }
        
        if (manufacturerLower.includes(query)) {
            score += 40;
        }
        
        // Model exact match
        if (modelLower === query) {
            score += 1500;
        }
        
        if (modelLower.includes(query)) {
            score += 30;
        }
        
        // Model number match (high priority)
        if (device.model_number?.toLowerCase() === query) {
            score += 4000;
        }
        
        if (device.model_number?.toLowerCase().includes(query)) {
            score += 60;
        }
        
        // Numeric model match (e.g., "5" in "Pixel 5")
        if (device.tokens.numericModel === query) {
            score += 1000;
        }
        
        // Region match
        if (device.region?.toLowerCase() === query) {
            score += 20;
        }
        
        // Product match
        if (device.products.some(p => p.toLowerCase() === query)) {
            score += 500;
        }
        
        if (device.products.some(p => p.toLowerCase().includes(query))) {
            score += 15;
        }
        
        // OS match
        if (device.os.toLowerCase() === query) {
            score += 200;
        }
        
        if (device.os.toLowerCase().includes(query)) {
            score += 10;
        }
        
        // Penalty for longer names (prefer shorter, more specific matches)
        score -= nameLower.length;
        
        return score;
    }
}

// Export for use in app.js
if (typeof window !== 'undefined') {
    window.DeviceSearchEngine = DeviceSearchEngine;
}
