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
          <Route index element={<Navigate to="/query" replace />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="schema" element={<SchemaPage />} />
          <Route path="query" element={<QueryPage />} />
          <Route path="results" element={<ResultsPage />} />
          <Route path="debug" element={<DebugPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
