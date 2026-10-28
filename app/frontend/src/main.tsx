import React from 'react';
import {createRoot} from 'react-dom/client';
import './theme/tokens.css';
import './styles/base.css';
import App from './app/App';
import './styles/terminal.css';
import './styles/glass.css';

const container = document.getElementById('root');
if (!container) throw new Error('Missing #root container');
createRoot(container).render(<App />);
