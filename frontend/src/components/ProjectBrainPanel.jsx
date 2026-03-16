import { useEffect, useState } from "react";
import {
  getProjectBrainStatus,
  getProjectSnapshot,
  searchProjectIndex,
  analyzeProjectGoal,
  createRefactorPlan,
} from "../api/project_brain";

export default function ProjectBrainPanel() {
  const [query, setQuery] = useState("");
  const [goal, setGoal] = useState("");
  const [status, setStatus] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [searchResult, setSearchResult] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const [statusData, snapshotData] = await Promise.all([
        getProjectBrainStatus(),
        getProjectSnapshot(),
      ]);
      setStatus(statusData);
      setSnapshot(snapshotData);
      setError("");
    } catch (err) {
      setError(String(err));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleSearch() {
    if (!query.trim()) return;
    try {
      const data = await searchProjectIndex(query.trim());
      setSearchResult(data);
      setError("");
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleAnalyze() {
    if (!goal.trim()) return;
    try {
      const data = await analyzeProjectGoal(goal.trim());
      setAnalysis(data);
      setError("");
    } catch (err) {
      setError(String(err));
    }
  }

  async function handlePlan() {
    if (!goal.trim()) return;
    try {
      const data = await createRefactorPlan(goal.trim());
      setPlan(data);
      setError("");
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <section className="workspace-card">
      <div className="section-header">
        <h2>Project Brain</h2>
        <button onClick={refresh}>Refresh</button>
      </div>

      <div className="goal-box">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Поиск по проектному индексу"
        />
        <button onClick={handleSearch}>Search Index</button>
      </div>

      <div className="goal-box">
        <input
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Например: Усиль архитектуру safe patch и dependency graph"
        />
        <button onClick={handleAnalyze}>Analyze Goal</button>
        <button onClick={handlePlan}>Create Plan</button>
      </div>

      {status ? (
        <div className="json-block">
          <h3>Status</h3>
          <pre>{JSON.stringify(status, null, 2)}</pre>
        </div>
      ) : null}

      {snapshot ? (
        <div className="json-block">
          <h3>Snapshot</h3>
          <pre>{JSON.stringify({
            files_count: snapshot.files_count,
            directories_count: snapshot.directories_count,
            duration_seconds: snapshot.duration_seconds,
          }, null, 2)}</pre>
        </div>
      ) : null}

      {searchResult ? (
        <div className="json-block">
          <h3>Search Result</h3>
          <pre>{JSON.stringify(searchResult, null, 2)}</pre>
        </div>
      ) : null}

      {analysis ? (
        <div className="json-block">
          <h3>Analysis</h3>
          <pre>{JSON.stringify(analysis, null, 2)}</pre>
        </div>
      ) : null}

      {plan ? (
        <div className="json-block">
          <h3>Refactor Plan</h3>
          <pre>{JSON.stringify(plan, null, 2)}</pre>
        </div>
      ) : null}

      {error ? <div className="panel-error">{error}</div> : null}
    </section>
  );
}
