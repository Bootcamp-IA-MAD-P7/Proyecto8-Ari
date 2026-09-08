import './TopBar.css'

// Brand chrome. Orange bar, sober clinical register (spec_front.md
// section 7). No logic — pure presentation.
function TopBar() {
  return (
    <header className="top-bar">
      <span className="top-bar__title">Hospital F5 · Servicio de Ictus</span>
    </header>
  )
}

export default TopBar
