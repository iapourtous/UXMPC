/**
 * Normalize MongoDB data by converting _id to id
 */
export function normalizeMongoData(data) {
  if (!data) return data;
  
  // Handle arrays
  if (Array.isArray(data)) {
    return data.map(item => normalizeMongoData(item));
  }
  
  // Handle objects
  if (typeof data === 'object') {
    const normalized = { ...data };
    
    // Convert _id to id
    if ('_id' in normalized && !('id' in normalized)) {
      normalized.id = normalized._id;
      delete normalized._id;
    }
    
    return normalized;
  }
  
  return data;
}