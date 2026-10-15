import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="au" style={{ padding: 24, textAlign: 'center' }}>
          <div className="card" style={{ maxWidth: 460, margin: 'auto' }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: 8 }}>Something went wrong</h2>
            <p className="mu" style={{ fontSize: '0.875rem', marginBottom: 16 }}>
              An unexpected error occurred while rendering this section.
            </p>
            <button
              type="button"
              className="btn"
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              style={{ width: '100%' }}
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
