export type WorkbenchBottomTab = "progress" | "logs" | "issues" | "artifacts";

export interface WorkbenchLayoutState {
  objectPaneCollapsed: boolean;
  inspectorCollapsed: boolean;
  bottomPaneCollapsed: boolean;
  objectPaneWidth: number;
  inspectorWidth: number;
  bottomPaneHeight: number;
  bottomTab: WorkbenchBottomTab;
}

export type WorkbenchLayoutAction =
  | { type: "toggleObjectPane" }
  | { type: "toggleInspector" }
  | { type: "toggleBottomPane" }
  | { type: "setObjectPaneWidth"; width: number }
  | { type: "setInspectorWidth"; width: number }
  | { type: "setBottomPaneHeight"; height: number }
  | { type: "setBottomTab"; tab: WorkbenchBottomTab };

export const initialWorkbenchLayoutState: WorkbenchLayoutState = {
  objectPaneCollapsed: false,
  inspectorCollapsed: false,
  bottomPaneCollapsed: false,
  objectPaneWidth: 300,
  inspectorWidth: 328,
  bottomPaneHeight: 220,
  bottomTab: "progress"
};

export function workbenchLayoutReducer(
  state: WorkbenchLayoutState,
  action: WorkbenchLayoutAction
): WorkbenchLayoutState {
  switch (action.type) {
    case "toggleObjectPane":
      return { ...state, objectPaneCollapsed: !state.objectPaneCollapsed };
    case "toggleInspector":
      return { ...state, inspectorCollapsed: !state.inspectorCollapsed };
    case "toggleBottomPane":
      return { ...state, bottomPaneCollapsed: !state.bottomPaneCollapsed };
    case "setObjectPaneWidth":
      return { ...state, objectPaneWidth: action.width };
    case "setInspectorWidth":
      return { ...state, inspectorWidth: action.width };
    case "setBottomPaneHeight":
      return { ...state, bottomPaneHeight: action.height };
    case "setBottomTab":
      return { ...state, bottomTab: action.tab };
    default:
      return state;
  }
}
