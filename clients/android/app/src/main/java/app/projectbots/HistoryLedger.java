package app.projectbots;
/** Memory-only presentation bookkeeping; no backend business rules. */
final class HistoryLedger {
 private long cursor;
 private final java.util.Set<Long> sequences=new java.util.HashSet<>();
 long cursor(){return cursor;}
 void advance(long next){cursor=Math.max(cursor,next);}
 boolean first(long sequence){return sequences.add(sequence);}
}
