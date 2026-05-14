import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import UploadPage from './pages/UploadPage';
import SchemaPage from './pages/SchemaPage';
import QueryPage from './pages/QueryPage';
import DebugPage from './pages/DebugPage';
import ResultsPage from './pages/ResultsPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/upload" replace />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="schema" element={<SchemaPage />} />
          <Route path="query" element={<QueryPage />} />
          <Route path="debug" element={<DebugPage />} />
          <Route path="results" element={<ResultsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
