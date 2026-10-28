import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";

export interface ScopeState {
  workspaceId: string;
  brandIds: string[];
  platforms: string[];
  accountIds: string[];
  contentAssetId?: string;
  publicationId?: string;
  dateRange: string;
}

const DEFAULT_SCOPE: ScopeState = {
  workspaceId: "ws_main",
  brandIds: [],
  platforms: [],
  accountIds: [],
  dateRange: "LAST_7_DAYS",
};

interface ScopeContextValue {
  scope: ScopeState;
  accounts: Array<Record<string, unknown>>;
  savedScopes: Array<Record<string, unknown>>;
  setScope: (patch: Partial<ScopeState>) => void;
  refreshAccounts: () => Promise<void>;
  saveScope: (name: string, favorite?: boolean) => Promise<void>;
}

const ScopeContext = createContext<ScopeContextValue | null>(null);

export function ScopeProvider({ children }: { children: React.ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [accounts, setAccounts] = useState<Array<Record<string, unknown>>>([]);
  const [savedScopes, setSavedScopes] = useState<Array<Record<string, unknown>>>([]);

  const scope = useMemo<ScopeState>(() => {
    return {
      workspaceId: searchParams.get("workspace") || DEFAULT_SCOPE.workspaceId,
      brandIds: (searchParams.get("brand") || "").split(",").filter(Boolean),
      platforms: (searchParams.get("platform") || "").split(",").filter(Boolean),
      accountIds: (searchParams.get("account") || "").split(",").filter(Boolean),
      contentAssetId: searchParams.get("content") || undefined,
      publicationId: searchParams.get("publication") || undefined,
      dateRange: searchParams.get("range") || DEFAULT_SCOPE.dateRange,
    };
  }, [searchParams]);

  const setScope = useCallback(
    (patch: Partial<ScopeState>) => {
      const next = { ...scope, ...patch };
      const params = new URLSearchParams();
      params.set("workspace", next.workspaceId);
      if (next.brandIds.length) params.set("brand", next.brandIds.join(","));
      if (next.platforms.length) params.set("platform", next.platforms.join(","));
      if (next.accountIds.length) params.set("account", next.accountIds.join(","));
      if (next.contentAssetId) params.set("content", next.contentAssetId);
      if (next.publicationId) params.set("publication", next.publicationId);
      params.set("range", next.dateRange);
      setSearchParams(params);
    },
    [scope, setSearchParams],
  );

  const refreshAccounts = useCallback(async () => {
    try {
      const rows = await api.accounts(scope.workspaceId);
      setAccounts(rows);
    } catch {
      setAccounts([]);
    }
  }, [scope.workspaceId]);

  useEffect(() => {
    void refreshAccounts();
    void api.savedScopes(scope.workspaceId).then(setSavedScopes).catch(() => setSavedScopes([]));
  }, [refreshAccounts, scope.workspaceId]);

  const saveScope = useCallback(
    async (name: string, favorite = false) => {
      const record = await api.createSavedScope({
        workspace_id: scope.workspaceId,
        name,
        scope: { ...scope },
        is_favorite: favorite,
        actor: "operator",
      });
      setSavedScopes((prev) => [record, ...prev]);
    },
    [scope],
  );

  return <ScopeContext.Provider value={{ scope, accounts, savedScopes, setScope, refreshAccounts, saveScope }}>{children}</ScopeContext.Provider>;
}

export function useScope(): ScopeContextValue {
  const value = useContext(ScopeContext);
  if (!value) throw new Error("useScope must be used within ScopeProvider");
  return value;
}
