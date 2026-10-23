import React from 'react';
import {Composition} from 'remotion';
import {Explainer} from './video';
import {fps, totalFrames} from './content';

export const Root: React.FC = () => (
  <Composition
    id="UptimeDeskExplainer"
    component={Explainer}
    durationInFrames={totalFrames}
    fps={fps}
    width={1920}
    height={1080}
  />
);
