# AEGIS UI Guidelines

# 1. Design Vision

AEGIS Control Center should feel like a premium developer product, not an open-source demo.

Keywords:
- Clean
- Professional
- Responsive
- Fast
- Minimal
- Smooth
- Consistent

Avoid:
- Glassmorphism overload
- Neon effects
- Busy dashboards
- Unnecessary animations

---

# 2. Theme

Primary Background: #0A0A0A
Secondary Background: #141414
Surface/Card: #1A1A1A
Border: #2A2A2A

Primary Accent: #FF7A00
Hover Accent: #FF922B

Primary Text: #FFFFFF
Secondary Text: #B8B8B8

Success: #22C55E
Warning: #FACC15
Error: #EF4444
Info: #60A5FA

---

# 3. Typography

Primary font:
- Inter
Fallback:
- system-ui
- sans-serif

Rules:
- clear hierarchy
- generous spacing
- avoid decorative fonts

---

# 4. Layout

Desktop:
- Left sidebar
- Top status bar
- Main content

Sidebar:
- Dashboard
- Provider Pool
- Runtime
- Analytics
- Logs
- Settings

Responsive:
- Sidebar collapses on tablet
- Drawer on mobile
- Cards stack vertically

---

# 5. Components

Buttons
- Primary: Orange
- Secondary: Dark outline
- Danger: Red
- Success: Green

Inputs
- Rounded corners
- Clear focus ring
- Inline validation

Cards
- Soft border
- Subtle hover
- No heavy shadows

Tables
- Compact
- Sticky header
- Search + filter

Badges
- Green = Healthy
- Red = Error
- Yellow = Warning
- Gray = Disabled

---

# 6. Dashboard

Widgets:
- Server Status
- Provider Pool Health
- Active Requests
- Average Latency
- Success Rate
- Error Rate

---

# 7. Provider Pool

Each provider card should show:
- Name
- Status
- Active Requests
- Recent Errors
- Latency
- Last Used
- Enable/Disable

Actions:
- Test
- Edit
- Remove

---

# 8. Runtime Page

Controls:
- Streaming
- Retry Count
- Timeout
- Scheduler Mode
- Cooldown
- Logging Level

---

# 9. Logs

Features:
- Search
- Filter
- Copy
- Timestamp
- Request ID
- Severity colors

---

# 10. Animations

Duration:
150–200 ms

Use:
- Hover
- Page transitions
- Loading skeletons

Avoid:
- Bounce
- Flash
- Long animations

---

# 11. Accessibility

- Keyboard navigation
- Visible focus states
- Sufficient color contrast
- Icons with labels
- Responsive text scaling

---

# 12. Empty & Loading States

Empty:
- Helpful message
- Primary action

Loading:
- Skeletons
- Progress indicators

---

# 13. Error & Success

Errors:
- Red accents
- Clear explanation
- Recovery action

Success:
- Green confirmation
- Short duration toast

---

# 14. Branding

Product:
AEGIS

UI Name:
AEGIS Control Center

Tagline:
Intelligent AI Gateway

---

# 15. Final Principle

Every screen should answer:
- What is happening?
- Is the server healthy?
- Which provider is active?
- Is user action required?

If those answers are visible within a few seconds, the UI is successful.
