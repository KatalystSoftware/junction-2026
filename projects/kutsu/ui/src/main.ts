import '@fontsource-variable/hanken-grotesk'
import './app.css'
import { mount } from 'svelte'
import App from './App.svelte'

const target = document.getElementById('app')
if (!target) throw new Error('index.html has no #app element to mount the page on')

export default mount(App, { target })
