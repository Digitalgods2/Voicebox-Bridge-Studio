import type { PlatformMetadata } from '@/platform/types';
import { version } from '../../package.json';

export const webMetadata: PlatformMetadata = {
  async getVersion(): Promise<string> {
    // Return version from env var or package.json
    return import.meta.env.VITE_APP_VERSION || version;
  },
  isTauri: false,
};
