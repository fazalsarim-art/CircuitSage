import type { BenchmarkVersion } from "./types";

interface Props {
  versions: BenchmarkVersion[];
  selectedId: string | null;
  onSelect: (version: BenchmarkVersion) => void;
}

export function VersionList({ versions, selectedId, onSelect }: Props) {
  return (
    <table className="doc-table">
      <caption className="sr-only">Benchmark versions</caption>
      <thead>
        <tr>
          <th scope="col">Name</th>
          <th scope="col">Version</th>
          <th scope="col">Status</th>
          <th scope="col">Cases</th>
          <th scope="col" />
        </tr>
      </thead>
      <tbody>
        {versions.map((version) => (
          <tr key={version.id} className={version.id === selectedId ? "selected" : undefined}>
            <td>{version.name}</td>
            <td>v{version.version}</td>
            <td>
              <span className={`badge status-${version.status === "published" ? "indexed" : "queued"}`}>
                {version.status}
              </span>
            </td>
            <td>{version.case_count}</td>
            <td>
              <button type="button" onClick={() => onSelect(version)}>
                {version.id === selectedId ? "Selected" : "Open"}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
