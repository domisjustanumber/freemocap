/**
 * The default RTMW keypoint confidence threshold (user T1), the same number as the backend's `RTMW_MIN_SCORE`.
 * The score is skellytracker's calibrated value in [0, 1]: 0.5 is even odds that the point is present and close to its
 * true position.
 */
export const RTMW_CONFIDENCE_THRESHOLD = 0.5;
