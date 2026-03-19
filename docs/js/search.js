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
        
        // Extract all numbers from name (e.g., ["5"] from "Pixel 5", ["13", "pro"] from "iPhone 13 Pro")
        const numbers = device.name.match(/\b(\d+[\w]*)\b/g);
        tokens.numbers = numbers ? numbers.map(n => n.toLowerCase()) : [];
        
        // Main model identifier (usually the first number)
        tokens.mainModel = tokens.numbers.length > 0 ? tokens.numbers[0] : '';
        
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
            'Oppo', 'Vivo', 'Realme', 'Asus', 'Xperia'
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
        
        // Extract numbers from query
        const numbers = queryLower.match(/\b(\d+[\w]*)\b/g);
        parsed.numbers = numbers ? numbers.map(n => n.toLowerCase()) : [];
        
        // Try to identify brand from query
        const brand = this.extractBrand(query);
        if (brand) {
            parsed.brand = brand.toLowerCase();
            // Extract everything after the brand as potential model
            const brandIndex = queryLower.indexOf(brand.toLowerCase());
            const afterBrand = queryLower.substring(brandIndex + brand.length).trim();
            if (afterBrand) {
                parsed.model = afterBrand;
                
                // Extract specific model number if present
                if (parsed.numbers.length > 0) {
                    parsed.modelNumber = parsed.numbers[0];
                }
            }
        } else {
            // No recognized brand found
            // Check if first word could be a brand (even if not in our list)
            if (parsed.isMultiWord) {
                parsed.possibleBrand = parts[0];
                parsed.restOfQuery = parts.slice(1).join(' ');
                
                if (parsed.numbers.length > 0) {
                    parsed.modelNumber = parsed.numbers[0];
                }
            } else if (parsed.numbers.length > 0) {
                // Single word with number (e.g., "5")
                parsed.modelNumber = parsed.numbers[0];
            }
        }
        
        return parsed;
    }
    
    search(query) {
        if (!query) return this.index;
        
        const parsedQuery = this.parseQuery(query);
        
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
        const deviceName = device.tokens.fullName;
        
        // Exact full name match
        if (deviceName === queryLower) {
            return true;
        }
        
        // For multi-word queries, ALL words must be present in the device name
        if (parsedQuery.isMultiWord) {
            const allWordsMatch = parsedQuery.parts.every(part => {
                // Each query word must appear in device name
                return deviceName.includes(part) || 
                       device.tokens.brand.includes(part) ||
                       device.tokens.model.includes(part) ||
                       device.tokens.modelNumber.includes(part) ||
                       device.tokens.manufacturer.includes(part);
            });
            
            if (!allWordsMatch) {
                // If not all words match, reject this device
                return false;
            }
        }
        
        // If query has brand + number (e.g., "pixel 5")
        if (parsedQuery.brand && parsedQuery.modelNumber) {
            const hasBrand = device.tokens.brand === parsedQuery.brand || 
                            deviceName.includes(parsedQuery.brand);
            
            const hasExactNumber = device.tokens.numbers.includes(parsedQuery.modelNumber);
            
            // MUST have BOTH brand AND number
            if (hasBrand && hasExactNumber) {
                return true;
            } else {
                // One of them is missing, reject
                return false;
            }
        }
        
        // If query has possible brand + number (unrecognized brand)
        if (parsedQuery.possibleBrand && parsedQuery.modelNumber) {
            const hasPossibleBrand = deviceName.includes(parsedQuery.possibleBrand);
            const hasExactNumber = device.tokens.numbers.includes(parsedQuery.modelNumber);
            
            // MUST have BOTH
            if (hasPossibleBrand && hasExactNumber) {
                return true;
            } else {
                return false;
            }
        }
        
        // Single word query with number (e.g., just "5")
        if (!parsedQuery.isMultiWord && parsedQuery.hasNumber) {
            // Allow single number searches to match any device with that number
            const hasExactNumber = device.tokens.numbers.includes(parsedQuery.modelNumber);
            return hasExactNumber;
        }
        
        // For queries without numbers, use word boundary matching
        const wordBoundaryPattern = new RegExp(`\\b${this.escapeRegex(queryLower)}\\b`, 'i');
        if (wordBoundaryPattern.test(deviceName)) {
            return true;
        }
        
        // Check model number
        if (device.tokens.modelNumber && device.tokens.modelNumber.includes(queryLower)) {
            return true;
        }
        
        // For single-word brand queries (e.g., just "pixel" or "samsung")
        if (!parsedQuery.isMultiWord && !parsedQuery.hasNumber) {
            // Check if query matches brand
            if (device.tokens.brand === queryLower || 
                deviceName.includes(queryLower) ||
                device.tokens.manufacturer === queryLower) {
                return true;
            }
        }
        
        // Fallback to general matching only for queries without numbers
        if (!parsedQuery.hasNumber) {
            const hasMatch = device.searchTerms.some(term => {
                if (!parsedQuery.isMultiWord) {
                    const pattern = new RegExp(`\\b${this.escapeRegex(queryLower)}`, 'i');
                    return pattern.test(term);
                }
                return term.includes(queryLower);
            });
            
            if (hasMatch) {
                return true;
            }
        }
        
        // Fuzzy match only for longer queries without numbers
        if (queryLower.length >= 4 && !parsedQuery.hasNumber) {
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
            score += 100000;
        }
        
        // Exact match with word boundaries
        const wordBoundaryPattern = new RegExp(`\\b${this.escapeRegex(query)}\\b`, 'i');
        if (wordBoundaryPattern.test(nameLower)) {
            score += 50000;
        }
        
        // Brand + Model number exact match (e.g., "pixel 5" matches "Google Pixel 5")
        if (parsedQuery.brand && parsedQuery.modelNumber) {
            const hasBrand = nameLower.includes(parsedQuery.brand);
            const hasExactNumber = device.tokens.numbers.includes(parsedQuery.modelNumber);
            
            if (hasBrand && hasExactNumber) {
                // Check if it's the exact model (not a variant like "5a" when searching "5")
                const modelPattern = new RegExp(`\\b${this.escapeRegex(parsedQuery.modelNumber)}\\b`, 'i');
                if (modelPattern.test(nameLower)) {
                    score += 80000; // Exact model
                } else {
                    score += 40000; // Model variant (e.g., 5a when searching 5)
                }
            }
        }
        
        // Exact number match in main model
        if (parsedQuery.numbers.length > 0 && device.tokens.mainModel === parsedQuery.numbers[0]) {
            score += 30000;
        }
        
        // Name starts with query
        if (nameLower.startsWith(query)) {
            score += 20000;
        }
        
        // Model number exact match
        if (device.model_number?.toLowerCase() === query) {
            score += 40000;
        }
        
        if (device.model_number?.toLowerCase().includes(query)) {
            score += 500;
        }
        
        // Manufacturer exact match
        if (manufacturerLower === query) {
            score += 15000;
        }
        
        // Model exact match
        if (modelLower === query) {
            score += 10000;
        }
        
        // Name contains query
        if (nameLower.includes(query)) {
            score += 1000;
        }
        
        // Product match
        if (device.products.some(p => p.toLowerCase() === query)) {
            score += 5000;
        }
        
        if (device.products.some(p => p.toLowerCase().includes(query))) {
            score += 100;
        }
        
        // OS match
        if (device.os.toLowerCase() === query) {
            score += 2000;
        }
        
        // Penalty for longer names (prefer shorter, more specific matches)
        score -= nameLower.length * 10;
        
        // Penalty for variant models when searching for base model
        // E.g., penalize "Pixel 5a" when searching "pixel 5"
        if (parsedQuery.modelNumber) {
            const exactPattern = new RegExp(`\\b${this.escapeRegex(parsedQuery.modelNumber)}\\b`, 'i');
            if (!exactPattern.test(nameLower)) {
                score -= 10000; // It's a variant, lower priority
            }
        }
        
        return score;
    }
}

// Export for use in app.js
if (typeof window !== 'undefined') {
    window.DeviceSearchEngine = DeviceSearchEngine;
}
