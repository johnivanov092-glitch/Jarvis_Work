export default function Phase21StatusStrip({
  phase20Queue,
  phase20State,
  phase21Run,
}) {
  const queueCount = phase20Queue?.items?.length || 0;
  const checkpoints = phase20State?.checkpoints?.length || 0;
  const controllerSteps = phase21Run?.controller?.steps?.length || 0;

  return (
    <div className="phase21-status-strip">
      <div className="project-map-chip">Queue: {queueCount}</div>
      <div className="project-map-chip">Checkpoints: {checkpoints}</div>
      <div className="project-map-chip">Controller: {controllerSteps}</div>
    </div>
  );
}
