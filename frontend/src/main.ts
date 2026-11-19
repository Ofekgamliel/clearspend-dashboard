import { createApp } from 'vue';
import App from './App.vue';
import './shared/theme/tokens.css';
import './shared/theme/palettes.css';
import './features/theme/theme.css';
import './features/events/events.css';
import './features/transactions/transactions.css';
import './features/recurring/recurring.css';
import './features/observations/observations.css';
import './features/imports/imports.css';
import './features/merchants/merchants.css';
import './style.css';

createApp(App).mount('#app');
