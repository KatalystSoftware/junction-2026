<script lang="ts">
  import Logo from './Logo.svelte'
  import { isComing, nameOf, reviewOf, stateNames } from './state.svelte'
  import type { Brief } from './types'

  // An event's employers as their logos, each ringed by how far its sign-up is. A logo opens the employer.
  let { briefs }: { briefs: Brief[] } = $props()
</script>

<ul>
  {#each briefs as brief, i (brief.id)}
    {@const status = reviewOf(brief).status}
    <li style:--i={i}>
      <a href="#/{encodeURIComponent(brief.id)}" class={status} title="{nameOf(brief)}: {stateNames(isComing(brief.id))[status].toLowerCase()}">
        <Logo {brief} small />
      </a>
    </li>
  {/each}
</ul>

<style>
  ul {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(3rem, 1fr));
    gap: var(--s2);
  }
  li {
    animation: rise 0.5s var(--ease) backwards;
    animation-delay: calc(var(--i) * 18ms);
  }
  a {
    display: block;
    aspect-ratio: 1;
    padding: 12%;
    border-radius: var(--r1);
    overflow: hidden;
    background: #fff;
    box-shadow: 0 0 0 1px var(--line);
    transition: transform 0.15s var(--ease), box-shadow 0.15s;
  }
  a:has(:global(.dark)) {
    background: #14151a;
  }
  a:hover {
    transform: translateY(-2px);
    box-shadow: 0 0 0 1px var(--ink-2);
  }
  a.invited {
    box-shadow: 0 0 0 2px var(--wait);
  }
  a.joined {
    box-shadow: 0 0 0 2px var(--ok);
  }
  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
  }
</style>
