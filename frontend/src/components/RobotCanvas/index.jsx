import { ROBOT_CONFIG } from "../../utils/constants";
import { fk_deg_to_svg, solveIK, clamp } from "../../services/kinematics";

export function RobotCanvas({ robot, onTargetClick, targetPoint, ikError }) {
  const { L1, L2, CENTER, LIMITS } = ROBOT_CONFIG;
  const { elbow, end } = fk_deg_to_svg(robot.j1, robot.j2);

  const handleClick = (e) => {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const svgX = e.clientX - rect.left;
    const svgY = e.clientY - rect.top;

    // Конвертация в координаты робота
    const robotX = svgX - CENTER;
    const robotY = -(svgY - CENTER);

    const result = solveIK(robotX, robotY);
    if (result) {
      const j1 = clamp(
        Math.round(result.j1 * 10) / 10,
        LIMITS.j1.min,
        LIMITS.j1.max,
      );
      const j2 = clamp(
        Math.round(result.j2 * 10) / 10,
        LIMITS.j2.min,
        LIMITS.j2.max,
      );
      onTargetClick?.({ j1, j2, x: robotX, y: robotY });
    } else {
      onTargetClick?.({ error: "⚠️ Точка вне рабочей зоны!" });
    }
  };

  return (
    <svg
      width="440"
      height="440"
      style={{ cursor: "crosshair" }}
      onClick={handleClick}
    >
      {/* Сетка, границы, звенья — как у тебя, но вынесено в отдельные компоненты при желании */}
      <circle cx={CENTER} cy={CENTER} r="6" fill="#111827" />
      <line
        x1={CENTER}
        y1={CENTER}
        x2={elbow.x}
        y2={elbow.y}
        stroke="#111827"
        strokeWidth="10"
      />
      <line
        x1={elbow.x}
        y1={elbow.y}
        x2={end.x}
        y2={end.y}
        stroke="#ef4444"
        strokeWidth="8"
      />
      {/* ... остальное ... */}
    </svg>
  );
}
