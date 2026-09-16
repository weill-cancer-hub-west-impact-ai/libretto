import { visit } from 'unist-util-visit';
import type { Element, Root } from 'hast';
import type { Annotation } from '$lib/extraction_types';

interface PluginOptions {
  annotations?: Annotation[];
  annotationClasses?: { [key: string]: string };
  annotationIconClasses?: { [key: string]: string };
  multipleAnnotationClasses?: string;
}

/**
 * Rehype plugin to transform custom HTML elements into Svelte components
 * with props from annotation data.
 */
export default function rehypeNoteComponents(options: PluginOptions = {}) {
  const {
    annotations = [],
    annotationClasses = {},
    annotationIconClasses = {},
    multipleAnnotationClasses = ''
  } = options;

  return (tree: Root) => {
    visit(tree, 'element', (node: Element) => {
      if (node.tagName === 'noteannotation' || node.tagName === 'NoteAnnotation') {
        // Get the position from the existing pos attribute
        const pos = parseInt(String(node.properties?.pos || '0'));

        // Find annotations that contain this position
        const relevantAnnotations = annotations.filter(
          (ann) =>
            !!ann.char_interval &&
            pos >= ann.char_interval.start_pos &&
            pos < ann.char_interval.end_pos
        );

        // Transform the node to have the component name and props
        node.tagName = 'noteannotation';

        // Set up properties/props for the Svelte component
        node.properties = {
          pos,
          annotations: relevantAnnotations,
          // Add CSS classes based on annotations
          className: getAnnotationClasses(
            relevantAnnotations,
            annotationClasses,
            multipleAnnotationClasses
          ),
          annotationIconClasses
        };
      }
    });
  };
}

/**
 * Helper function to determine CSS classes for annotations
 */
function getAnnotationClasses(
  annotations: Annotation[],
  annotationClasses: { [key: string]: string },
  multipleAnnotationClasses: string
): string {
  let uniqueSources = new Set(annotations.map((ann) => ann.source));
  if (uniqueSources.size === 0) return '';

  if (uniqueSources.size === 1) {
    return annotationClasses[Array.from(uniqueSources)[0]] || '';
  }

  // Multiple annotations - combine classes or use special multiple class
  if (multipleAnnotationClasses) {
    return multipleAnnotationClasses;
  }

  // Combine individual classes
  const classes = annotations
    .map((ann) => annotationClasses[ann.source])
    .filter(Boolean)
    .join(' ');

  return classes;
}
