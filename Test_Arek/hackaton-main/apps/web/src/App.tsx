import { useState } from 'react'
import axios from 'axios'
import './index.css'

const API_BASE = 'http://localhost:8000';

function App() {
  const [results, setResults] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  // Default to the seeded UUID
  const [actId, setActId] = useState('f71df335-32cd-40a5-9326-5cfe00c0e828');
  const [question, setQuestion] = useState('Co to za ustawa? Podaj szczegóły.');
  const [description, setDescription] = useState('Analiza wpływu zmiany podatku VAT na małe przedsiębiorstwa.');
  const [patentQuery, setPatentQuery] = useState('metoda filtrowania spalin samochodowych');

  const callApi = async (name: string, method: 'get' | 'post', endpoint: string, data?: any) => {
    setLoading(prev => ({ ...prev, [name]: true }));
    try {
      const response = await (method === 'get' 
        ? axios.get(`${API_BASE}${endpoint}`)
        : axios.post(`${API_BASE}${endpoint}`, data));
      setResults(prev => ({ ...prev, [name]: response.data }));
    } catch (error: any) {
      setResults(prev => ({ ...prev, [name]: error.response?.data || error.message }));
    } finally {
      setLoading(prev => ({ ...prev, [name]: false }));
    }
  };

  return (
    <div className="dashboard">
      <h1>CivicLens - Dashboard Testowy</h1>
      
      <div className="section">
        <h2>1. System Health</h2>
        <button onClick={() => callApi('health', 'get', '/health')}>Check Health</button>
        {loading['health'] && <p>Loading...</p>}
        {results['health'] && <pre>{JSON.stringify(results['health'], null, 2)}</pre>}
      </div>

      <div className="section">
        <h2>2. Legal Acts</h2>
        <button onClick={() => callApi('acts', 'get', '/api/legal-acts')}>List Acts</button>
        <div style={{ marginTop: '10px' }}>
          <input value={actId} onChange={e => setActId(e.target.value)} placeholder="Act ID (UUID)" style={{ width: '350px' }} />
          <button onClick={() => callApi('act_detail', 'get', `/api/legal-acts/${actId}`)}>Get Details</button>
        </div>
        {loading['acts'] && <p>Loading...</p>}
        {results['acts'] && <pre>{JSON.stringify(results['acts'], null, 2)}</pre>}
        {results['act_detail'] && <pre>{JSON.stringify(results['act_detail'], null, 2)}</pre>}
      </div>

      <div className="section">
        <h2>3. AI Q&A</h2>
        <input value={actId} onChange={e => setActId(e.target.value)} placeholder="Act ID" style={{ width: '350px' }} />
        <br/><br/>
        <input value={question} onChange={e => setQuestion(e.target.value)} placeholder="Question" style={{ width: '500px' }} />
        <button onClick={() => callApi('qa', 'post', '/api/qa', { act_id: actId, question, top_k: 5 })}>Ask AI</button>
        <p><small>Uwaga: AI musi zwrócić cytaty, inaczej zadziała Guardrail.</small></p>
        {loading['qa'] && <p>Thinking...</p>}
        {results['qa'] && <pre>{JSON.stringify(results['qa'], null, 2)}</pre>}
      </div>

      <div className="section">
        <h2>4. Impact Analysis</h2>
        <input value={actId} onChange={e => setActId(e.target.value)} placeholder="Act ID" style={{ width: '350px' }} />
        <br/><br/>
        <textarea 
            value={description} 
            onChange={e => setDescription(e.target.value)} 
            placeholder="Opis do analizy wpływu" 
            style={{ width: '500px', height: '60px' }} 
        />
        <br/>
        <button onClick={() => callApi('impact', 'post', '/api/analyze/impact', { act_id: actId, description, top_k: 5 })}>Analyze Impact</button>
        {loading['impact'] && <p>Analyzing...</p>}
        {results['impact'] && <pre>{JSON.stringify(results['impact'], null, 2)}</pre>}
      </div>

      <div className="section">
        <h2>5. Patent Check</h2>
        <textarea 
            value={patentQuery} 
            onChange={e => setPatentQuery(e.target.value)} 
            placeholder="Opis pomysłu do sprawdzenia w patentach" 
            style={{ width: '500px', height: '60px' }} 
        />
        <br/>
        <button onClick={() => callApi('patent', 'post', '/api/analyze/patent-check', { idea_description: patentQuery, top_k: 5 })}>Check Patents</button>
        {loading['patent'] && <p>Checking patents...</p>}
        {results['patent'] && <pre>{JSON.stringify(results['patent'], null, 2)}</pre>}
      </div>

      <div className="section">
        <h2>6. Trends</h2>
        <button onClick={() => callApi('trends', 'post', '/api/analyze/trends', { topic: "gospodarka" })}>Analyze Trends</button>
        {loading['trends'] && <p>Analyzing trends...</p>}
        {results['trends'] && <pre>{JSON.stringify(results['trends'], null, 2)}</pre>}
      </div>

      <div className="section">
        <h2>7. Auth Login</h2>
        <button onClick={() => callApi('login', 'post', '/auth/login', {})}>Login Stub</button>
        {results['login'] && <pre>{JSON.stringify(results['login'], null, 2)}</pre>}
      </div>
    </div>
  )
}

export default App
