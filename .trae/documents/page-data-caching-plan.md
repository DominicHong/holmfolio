# Page Data Caching Plan

## Context

Currently, every sidebar navigation in NiceAMS destroys and recreates the view component, causing `onMounted` to re-fetch all data from the backend. This creates unnecessary API traffic and slow page transitions when navigating back to a previously visited page. The user wants pages to display cached data on re-navigation, with explicit refresh controls for fetching new data.

## Approach: Vue `<keep-alive>` on router-view

Wrap `<router-view>` with `<keep-alive :include>` so component instances (and all their reactive state, local refs, form inputs, scroll position) are preserved across navigation. Add refresh buttons to each page so users can explicitly trigger fresh data fetches.

**Why this approach:**
- Preserves exactly the "last displayed data" the user wants — component state stays intact
- No API calls on re-navigation — `onMounted` only fires once (first visit)
- Financial.vue's local refs (direct axios, no store) are automatically preserved
- Minimal code change — no store refactoring needed
- `<keep-alive>` is a built-in Vue 3 feature

**PositionDetail is excluded** from keep-alive because it has dynamic route params (`/positions/:assetId`) — caching it would show stale data when navigating between different assets.

## Files to Modify (11 files, no new files)

### 1. `frontend/src/App.vue`
- Add `cachedViewNames` array listing 8 sidebar page component names
- Wrap `<router-view />` with `<keep-alive :include="cachedViewNames" :max="8">` using the `v-slot="{ Component }"` pattern
- Import `Refresh` icon from `@element-plus/icons-vue`

### 2–9. View Components (8 sidebar pages)
For each: add `defineOptions({ name: 'ViewName' })`, import `Refresh` icon, add a circular refresh button in the page header area, add `handleRefresh` function that calls the view's existing initialization function.

| View | Component Name | Refresh Action |
|------|---------------|----------------|
| `Dashboard.vue` | `Dashboard` | `initializeDashboard()` |
| `Portfolio.vue` | `Portfolio` | `initializePortfolio()` |
| `Financial.vue` | `Financial` | `handleShowFinancials()` |
| `Transactions.vue` | `Transactions` | `initializeData()` |
| `Assets.vue` | `Assets` | `Promise.all([fetchAssets, fetchCurrencies])` |
| `TagManagement.vue` | `TagManagement` | `Promise.all([fetchTagCategories, fetchTags, fetchAssets])` |
| `Analytics.vue` | `Analytics` | `initializeAnalytics()` |
| `Settings.vue` | `Settings` | sequential: `fetchCurrencies → loadSettings → loadExchangeRates → loadBenchmarks` |

### 10. `frontend/src/views/PositionDetail.vue`
- Add `defineOptions({ name: 'PositionDetail' })` only — excluded from keep-alive, no refresh button

### 11. `frontend/src/router/index.ts`
- Add `meta: { keepAlive: true/false }` to each route for documentation

## Implementation Order

1. Add `defineOptions({ name })` to all 9 view components (prerequisite for keep-alive matching)
2. Modify `App.vue` — wrap `<router-view>` with `<keep-alive>` (core change)
3. Add refresh buttons + `handleRefresh` to all 8 cached views
4. Add route `meta` fields to `router/index.ts`
5. Manual testing

## Edge Cases

- **Open dialogs on navigation:** Keep-alive preserves dialog state. Accepted as-is (consistent with caching goal).
- **Portfolio watchers:** Dashboard/Analytics watchers on `currentPortfolio` remain active while deactivated — this means store-level changes propagate to cached views automatically (desirable).
- **Chart.js canvases:** Preserved by keep-alive, Chart.js instances remain valid.
- **Memory:** `:max="8"` caps cached instances. All 8 sidebar pages fit exactly.

## Verification

1. Navigate Dashboard → Portfolio → Dashboard — should show cached data, no API calls in DevTools Network tab
2. Click Refresh on Dashboard — should fetch fresh data from API
3. Navigate to PositionDetail(1) → PositionDetail(2) — each should fetch its own data (not cached)
4. Open a dialog → navigate away → return — dialog should still be open
5. Change portfolio on one page → navigate to Dashboard — should reflect updated portfolio (store reactivity)
