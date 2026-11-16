import { createContext } from 'react';
import type { OutputFileScope } from '@/lib/output-files';

export const OutputFileContext = createContext<OutputFileScope | null>(null);
