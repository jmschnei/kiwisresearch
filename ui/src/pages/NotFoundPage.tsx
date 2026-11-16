import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="page-scroll flex flex-col items-center justify-center gap-4 text-gray-400">
      <div className="text-5xl">🧭</div>
      <div className="text-lg">Página no encontrada</div>
      <Link to="/" className="btn-primary">
        Volver al inicio
      </Link>
    </div>
  );
}
