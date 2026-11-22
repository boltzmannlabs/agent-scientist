import { useCallback, useState } from "react";

export const useCenteredTree = () => {
  const [translate, setTranslate] = useState({ x: 0, y: 0 });
  const containerRef = useCallback((containerElem) => {
    if (containerElem === null) return;

    containerElem._sciTreeResizeObserver?.disconnect();
    const updateTranslate = () => {
      const { width, height } = containerElem.getBoundingClientRect();
      setTranslate({ x: width / 2, y: height / 10 });
    };

    updateTranslate();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(updateTranslate);
    observer.observe(containerElem);
    containerElem._sciTreeResizeObserver = observer;
  }, []);
  return [translate, containerRef];
};
export const useCenteredTree2 = () => {
  const [translate2, setTranslate2] = useState({ x: '50%', y:'50%'  });
  const containerRef2 = useCallback((containerElem) => {
    if (containerElem !== null) {
      const { width, height } = containerElem.getBoundingClientRect();
      setTranslate2({ x: width / 4, y: height / 10 });
    }
  }, []);
  return [translate2, containerRef2];
};
export const useCenteredTree3 = () => {
  const [translate3, setTranslate2] = useState({ x: 0, y: 0 });
  const containerRef3 = useCallback((containerElem) => {
    if (containerElem !== null) {
      const { width, height } = containerElem.getBoundingClientRect();
      setTranslate2({ x: width / 2, y: height / 10 });
    }
  }, []);
  return [translate3, containerRef3];
};
