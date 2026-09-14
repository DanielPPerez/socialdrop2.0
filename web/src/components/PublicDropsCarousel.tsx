"use client"

import { useEffect, useRef, useState } from "react"
import useEmblaCarousel from "embla-carousel-react"
import { ChevronLeft, ChevronRight, ArrowUpRight, Loader2 } from "lucide-react"
import { PublicDrop } from "@/lib/api"
import Link from "next/link"
import { cn } from "@/lib/utils"

interface PublicDropsCarouselProps {
  drops: PublicDrop[]
}

function ScrollButtons({
  emblaApi,
  orientation = "horizontal",
}: {
  emblaApi: ReturnType<typeof useEmblaCarousel>[1] | undefined
  orientation?: "horizontal" | "vertical"
}) {
  if (!emblaApi) return null

  const [scrollPrev, setScrollPrev] = useState(false)
  const [scrollNext, setScrollNext] = useState(false)

  useEffect(() => {
    if (!emblaApi) return

    const update = () => {
      setScrollPrev(emblaApi.canScrollPrev())
      setScrollNext(emblaApi.canScrollNext())
    }

    emblaApi.on("reInit", update).on("select", update)
    update()

    return () => {
      emblaApi.off("reInit", update).off("select", update)
    }
  }, [emblaApi])

  const scrollPrevHandler = () => emblaApi.scrollPrev()
  const scrollNextHandler = () => emblaApi.scrollNext()

  return (
    <div
      className={cn(
        "flex gap-2",
        orientation === "horizontal" && "items-center",
        orientation === "vertical" && "flex-col justify-center"
      )}
      role="group"
      aria-label="Carousel navigation"
    >
      <button
        type="button"
        onClick={scrollPrevHandler}
        disabled={!scrollPrev}
        aria-label="Previous"
        className={cn(
          "p-2 rounded-full bg-white/80 backdrop-blur-sm border border-gray-200",
          "hover:bg-white hover:border-gray-300 active:scale-[0.98]",
          "disabled:opacity-40 disabled:cursor-not-allowed",
          "transition-all duration-200",
          "shadow-sm"
        )}
      >
        <ChevronLeft className="h-5 w-5 text-gray-700" aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={scrollNextHandler}
        disabled={!scrollNext}
        aria-label="Next"
        className={cn(
          "p-2 rounded-full bg-white/80 backdrop-blur-sm border border-gray-200",
          "hover:bg-white hover:border-gray-300 active:scale-[0.98]",
          "disabled:opacity-40 disabled:cursor-not-allowed",
          "transition-all duration-200",
          "shadow-sm"
        )}
      >
        <ChevronRight className="h-5 w-5 text-gray-700" aria-hidden="true" />
      </button>
    </div>
  )
}

export function PublicDropsCarousel({ drops }: PublicDropsCarouselProps) {
  const [emblaRef, emblaApi] = useEmblaCarousel({
    loop: false,
    align: "start",
    slidesToScroll: 1,
    breakpoints: {
      "(min-width: 640px)": { slidesToScroll: 1 },
      "(min-width: 1024px)": { slidesToScroll: 1 },
    },
  })

  const [selectedIndex, setSelectedIndex] = useState(0)
  const scrollSnaps = emblaApi?.scrollSnapList()

  useEffect(() => {
    if (!emblaApi) return
    const onSelect = () => setSelectedIndex(emblaApi.selectedScrollSnap())
    emblaApi.on("select", onSelect)
    onSelect()
    return () => {
      emblaApi.off("select", onSelect)
    }
  }, [emblaApi])

  const scrollPrev = () => emblaApi?.scrollPrev()
  const scrollNext = () => emblaApi?.scrollNext()

  if (drops.length === 0) {
    return (
      <div className="py-16 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 mb-4">
          <Loader2 className="h-8 w-8 text-gray-400 animate-spin" />
        </div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">No hay contenido público aún</h3>
        <p className="text-gray-500 max-w-sm mx-auto">
          Cuando publiques tu primer drop con <code className="px-1.5 py-0.5 bg-gray-100 rounded text-sm font-mono">public: true</code>,
          aparecerá aquí automáticamente.
        </p>
      </div>
    )
  }

  return (
    <div className="relative">
      <div className="overflow-hidden" ref={emblaRef}>
        <div className="flex gap-4 pb-4" style={{ touchAction: "pan-y pinch-zoom" }}>
          {drops.map((drop, index) => (
            <div
              key={drop.id}
              className={cn(
                "flex-[0_0_100%] min-w-0",
                "sm:flex-[0_0_calc(50%-2rem)]",
                "lg:flex-[0_0_calc(33.333%-2.67rem)]",
                "xl:flex-[0_0_calc(25%-3rem)]"
              )}
            >
              <article className="h-full bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow duration-300 overflow-hidden flex flex-col">
                <div className="aspect-video bg-gray-100 relative overflow-hidden">
                  {drop.thumbnail_url ? (
                    <img
                      src={drop.thumbnail_url}
                      alt={drop.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-gray-100 to-gray-200">
                      <Loader2 className="h-8 w-8 text-gray-400 animate-spin" />
                    </div>
                  )}
                  {drop.platforms.length > 0 && (
                    <div className="absolute top-3 right-3 flex gap-1.5 flex-wrap">
                      {drop.platforms.slice(0, 3).map((p) => (
                        <span
                          key={p.name}
                          className="px-2 py-1 text-xs font-medium rounded-full bg-white/90 backdrop-blur-sm text-gray-700 border border-gray-200"
                        >
                          {p.name}
                        </span>
                      ))}
                      {drop.platforms.length > 3 && (
                        <span className="px-2 py-1 text-xs font-medium rounded-full bg-white/90 backdrop-blur-sm text-gray-500 border border-gray-200">
                          +{drop.platforms.length - 3}
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className="p-4 flex flex-col flex-1">
                  <h4 className="font-semibold text-gray-900 text-base mb-2 line-clamp-2">
                    {drop.title}
                  </h4>
                  {drop.published_at && (
                    <time
                      className="text-sm text-gray-500 mb-3"
                      dateTime={drop.published_at}
                    >
                      Publicado el{" "}
                      {new Date(drop.published_at).toLocaleDateString("es-ES", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </time>
                  )}
                  <Link
                    href={`/drops/${drop.id}`}
                    className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors mt-auto"
                  >
                    Ver detalles
                    <ArrowUpRight className="h-4 w-4" />
                  </Link>
                </div>
              </article>
            </div>
          ))}
        </div>
      </div>

      {(scrollSnaps && scrollSnaps.length > 1) && (
        <div className="flex justify-center mt-4">
          <ScrollButtons emblaApi={emblaApi} />
        </div>
      )}

      <div className="flex justify-center gap-1.5 mt-4" role="tablist" aria-label="Carousel indicators">
        {scrollSnaps?.map((_, index) => (
          <button
            key={index}
            role="tab"
            aria-selected={index === selectedIndex}
            aria-label={`Go to slide ${index + 1}`}
            onClick={() => emblaApi?.scrollTo(index)}
            className={cn(
              "w-2 h-2 rounded-full transition-all duration-200",
              index === selectedIndex
                ? "bg-blue-600 w-6"
                : "bg-gray-300 hover:bg-gray-400"
            )}
          />
        ))}
      </div>
    </div>
  )
}