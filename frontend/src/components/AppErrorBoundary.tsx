import { Component, ErrorInfo, ReactNode } from 'react';
import { Link } from 'react-router-dom';

type Props = { children: ReactNode };
type State = { failed: boolean };

export default class AppErrorBoundary extends Component<Props, State> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('MatchFit screen crashed', error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return <main className="auth-page"><section className="auth-card stack"><span className="brand">MatchFit <b>Pro</b></span><h1>Screen did not load</h1><p className="error">MatchFit hit a page error. Refresh once, then return to the dashboard if it continues.</p><div className="actions"><button onClick={() => location.reload()}>Refresh</button><Link className="button secondary" to="/dashboard" onClick={() => this.setState({ failed: false })}>Dashboard</Link></div></section></main>;
  }
}
