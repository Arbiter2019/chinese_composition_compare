import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Simulate from './pages/Simulate'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/simulate" element={<Simulate />} />
        <Route path="*" element={<Navigate to="/simulate" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
