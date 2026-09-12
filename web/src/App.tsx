import { useEffect } from "react";
import { Route, Routes, useNavigate, useParams } from "react-router-dom";
import { Viewer } from "./components/Viewer";
import { SidePanel } from "./components/SidePanel";
import { SearchBox } from "./components/SearchBox";
import { LayerToggles } from "./components/LayerToggles";
import { ViewControls } from "./components/ViewControls";
import { RegionTree } from "./components/RegionTree";
import { useStore } from "./store";

// Deep links: /s/FMA:22356 opens directly on a structure (design doc §8). The URL is the
// source of truth for the selection; clicks in the viewer navigate, and the route syncs the store.
function Explorer() {
  const { id } = useParams();
  const selectedId = useStore((s) => s.selectedId);
  const select = useStore((s) => s.select);
  const load = useStore((s) => s.load);
  const treeOpen = useStore((s) => s.treeOpen);
  const navigate = useNavigate();

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if ((id ?? null) !== selectedId) select(id ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    const target = selectedId ? `/s/${selectedId}` : "/";
    if (window.location.pathname !== target) navigate(target, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  return (
    <div className="flex h-full">
      {treeOpen && (
        <aside className="w-72 shrink-0 border-r border-neutral-800 bg-neutral-900">
          <RegionTree />
        </aside>
      )}
      <main className="relative flex-1">
        <Viewer />
        <div className="absolute inset-x-3 bottom-3 flex flex-col gap-2 md:w-[36rem]">
          <ViewControls />
          <LayerToggles />
          <SearchBox />
        </div>
      </main>
      <aside className="w-full max-w-md border-l border-neutral-800 bg-neutral-900">
        <SidePanel structureId={selectedId} />
      </aside>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Explorer />} />
      <Route path="/s/:id" element={<Explorer />} />
    </Routes>
  );
}
