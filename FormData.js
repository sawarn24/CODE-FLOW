const mongoose = require('mongoose');

const formDataSchema = new mongoose.Schema({
  businessName: String,
  businessType: String,
  businessCategory: String,
  location: String,
  businessTone: String,
  offer: String,
  targetAudience: String,
  platformFocus: [String],
  userId: String,        // ✅ Add this
  userEmail: String,     // ✅ And this
  createdAt: { type: Date, default: Date.now }
});

module.exports = mongoose.model('FormData', formDataSchema);