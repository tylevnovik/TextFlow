import type { CSSProperties, ReactNode } from "react";
import { FluentProvider } from "@fluentui/react-components";
import { textFlowCssVariables, textFlowFluentTheme } from "./fluentTheme";

interface AppShellProps {
  children: ReactNode;
  uiScale: number;
}

export function AppShell({ children, uiScale }: AppShellProps) {
  const shellStyle = {
    transform: `scale(${uiScale})`,
    transformOrigin: "top left",
    width: `${100 / uiScale}%`,
    height: `calc(100vh / ${uiScale})`,
    minHeight: `calc(100vh / ${uiScale})`
  } as CSSProperties;

  return (
    <FluentProvider theme={textFlowFluentTheme} className="textflow-fluent-provider" style={textFlowCssVariables as CSSProperties}>
      <div className="app-shell-frame">
        <div className="background-grid" />
        <div className="textflow-workbench-scale" style={shellStyle}>
          {children}
        </div>
      </div>
    </FluentProvider>
  );
}
