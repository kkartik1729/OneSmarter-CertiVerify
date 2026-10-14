import { Link } from 'react-router-dom';

/** 404 page. */
export default function NotFound() {
  return (
    <div className="ms"><div>
      <h1>404</h1><h2>Page not found</h2>
      <p className="mu">That page doesn’t exist.</p>
      <Link className="btn" to="/">Back to home</Link>
    </div></div>
  );
}
