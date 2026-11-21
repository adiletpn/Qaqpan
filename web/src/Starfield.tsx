import './starfield.css'

// Pure-CSS parallax starfield (scripts/make_starfield.py): three layers, only transform animates.
export default function Starfield() {
  return (
    <div className="starfield" aria-hidden>
      <div className="stars-s" /><div className="stars-m" /><div className="stars-l" />
    </div>
  )
}
