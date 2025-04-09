const express = require('express');
const mongoose = require('mongoose');
const session = require('express-session');
const bcrypt = require('bcrypt');
const path = require('path');
const User = require('./models/User');

const app = express();

// Connect MongoDB
mongoose.connect('mongodb://localhost:27017/brandspark_auth', {
  useNewUrlParser: true,
  useUnifiedTopology: true
});

// Middleware
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Session setup
app.use(session({
  secret: 'brandspark-secret',
  resave: false,
  saveUninitialized: false
}));

// Routes
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public/login.html'));
});

app.get('/register', (req, res) => {
  res.sendFile(path.join(__dirname, 'public/register.html'));
});

app.post('/register', async (req, res) => {
  const { name, email, password, confirmPassword } = req.body;

  if (password !== confirmPassword) {
    return res.status(400).send('Passwords do not match');
  }

  const existingUser = await User.findOne({ email });
  if (existingUser) return res.status(400).send('User already exists');

  const hashedPassword = await bcrypt.hash(password, 10);
  const newUser = new User({ name, email, password: hashedPassword });
  await newUser.save();

  req.session.user = {
    id: newUser._id,
    name: newUser.name,
    email: newUser.email
  };

  res.redirect(`/dashboard/${newUser._id}`);
});

app.post('/login', async (req, res) => {
    const { email, password } = req.body;
    const user = await User.findOne({ email });
  
    if (!user || !(await bcrypt.compare(password, user.password))) {
      return res.status(401).send('Invalid credentials');
    }
  
    // FIX: store full user info in session
    req.session.user = {
      id: user._id,
      name: user.name,
      email: user.email
    };
  
    res.redirect(`/dashboard/${user._id}`);

  });

  app.get('/dashboard/:id', (req, res) => {
    const sessionUser = req.session.user;
  
    if (!sessionUser || sessionUser.id !== req.params.id) {
      return res.redirect('/login');
    }
  
    res.sendFile(path.join(__dirname, 'public/dashboard.html')); // ✅ serve real file
  });  

// ✅ Logout route
app.get('/logout', (req, res) => {
  req.session.destroy(err => {
    if (err) {
      return res.send('Error logging out');
    }
    res.redirect('/');
  });
});

app.get('/api/me', (req, res) => {
    if (!req.session.user) {
      return res.status(401).json({ message: 'Unauthorized' });
    }
    res.json(req.session.user);
  });


const FormData = require('./models/FormData');

app.post('/submit-form', async (req, res) => {
  try {
    const formEntry = new FormData(req.body);
    await formEntry.save();
    res.send('Form submitted successfully');
  } catch (err) {
    console.error(err);
    res.status(500).send('Error saving form');
  }
});

  
app.get('/api/user-info', (req, res) => {
    if (!req.session.user) {
      return res.status(401).json({ message: 'Not logged in' });
    }
    res.json(req.session.user);
  });
  

app.get('/form', (req, res) => {
  if (!req.session.user) {
    return res.redirect('/login');
  }
  res.sendFile(path.join(__dirname, 'public/form.html'));
});


app.listen(3000, () => {
  console.log('🚀 Server running at http://localhost:3000');
});
