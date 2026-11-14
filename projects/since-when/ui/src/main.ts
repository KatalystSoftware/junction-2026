import '@wikimedia/codex-design-tokens/theme-wikimedia-ui.css'
// Codex's CSS-only components: only the stylesheets of the ones the markup uses, and none of its
// Vue code.
import '@wikimedia/codex/dist/modules/CdxButton.css'
import '@wikimedia/codex/dist/modules/CdxField.css'
import '@wikimedia/codex/dist/modules/CdxLabel.css'
import '@wikimedia/codex/dist/modules/CdxSearchInput.css'
import '@wikimedia/codex/dist/modules/CdxSelect.css'
import '@wikimedia/codex/dist/modules/CdxTextInput.css'
import './app.css'
import { mount } from 'svelte'
import App from './App.svelte'

export default mount(App, { target: document.getElementById('app')! })
