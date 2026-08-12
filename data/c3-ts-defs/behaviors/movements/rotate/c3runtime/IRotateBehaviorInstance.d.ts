
type RotationBehaviorRotationType = "2d" | "rotation-x" | "rotation-y" | "rotation-z";

/** Represents the Rotate behavior.
 * @see {@link https://www.construct.net/make-games/manuals/construct-3/scripting/scripting-reference/behavior-interfaces/rotate | IRotateBehaviorInstance documentation } */
declare class IRotateBehaviorInstance<InstType> extends IBehaviorInstance<InstType>
{
	speed: number;
	acceleration: number;
	rotationType: RotationBehaviorRotationType;
	isEnabled: boolean;
}
