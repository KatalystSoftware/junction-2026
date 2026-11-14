import '@wikimedia/codex-design-tokens/theme-wikimedia-ui.css'
// Codex's CSS-only components: only the stylesheets of the ones the markup uses, and none of its
// Vue code.
import '@wikimedia/codex/dist/modules/CdxButton.css'
import './app.css'
import { mount } from 'svelte'
import App from './App.svelte'

export default mount(App, { target: document.getElementById('app')! })
