class DNSFormSwitcher{
    /**
     * Manages DNS form switching from Alpine Data
     * Requires an HTML container with Alpine.js initialized on it
     * 
     * State:
     * - pending: an object { type, recordId} representing the form the user is currently on
     *   type is either "edit" or "add", recordID is the form's recordID
     * - target: the form  ID the user is clicking to.
     * 
     * Methods
     * - attemptOpen: sets the pending object on the class instance
     * - switchForm: performs the actual form switch, and resets the pending and target
     *   - uses methods setShowId, and resetPendingAndTarget methods
     * - getAlpineData: returns the Alpine data object for the container
     *
    */ 
   
    constructor(container){
        this.pending = null;
        this.target = null;
        this.container = container;
    }

    setPending(value) {
         this.pending = value;
    }


    getAlpineData(){
        return Alpine.$data(this.container);
    }


    resetPendingAndTarget(){
       this.setTarget(null);
       this.setPending(null);
    }

}

export class EditFormSwitcher extends DNSFormSwitcher{

    setTarget(value){  
        const current = this.getCurrentShowFormId();
        this.target = current == value ? null : value;
    }

    setShowId(value){
        const data = this.getAlpineData();
        data.showFormId = value;
    }
   
    switchForm(value = this.target){
       this.setShowId(value);
       this.resetPendingAndTarget();
    }

    getCurrentShowFormId(){
        return this.getAlpineData().showFormId
    }
   
    attemptOpen(form){
        this.setTarget(form);
        const currentId = this.getCurrentShowFormId();
        const req = {
            type: currentId > 0 ? "edit" : "add",
            recordId: currentId
        }
         this.setPending(req);
    }

    switchForm(value = this.target){
       this.setShowId(value);
       this.resetPendingAndTarget();
    }
}

export class RecordSelectTypeSwitcher extends DNSFormSwitcher{

    constructor(container){
        super(container);
        this.isRecordType = true;
    }

    setTarget(value){
        this.target = value;
    }

    setRecordType(value = this.target){
        const data = this.getAlpineData();
        data.recordType = this.target;
    }

    attemptOpen(form){
        this.setTarget(form);
        const currentId = this.getAlpineData().recordType;
        const req = {
            type: 'add',
            recordId: currentId,
            isRecordType: this.isRecordType
        }

         this.setPending(req);
    }

    updateSelectedType(value = this.target){
        this.container.selectedIndex = value;
    }

    switchForm(){
       this.setRecordType(this.target);
       this.updateSelectedType();
       this.resetPendingAndTarget();
    }
}